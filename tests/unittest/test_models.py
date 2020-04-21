# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.


import os
import sys
import warnings

import mxnet as mx
import pytest
from mxnet import gluon

import gluonnlp as nlp
from gluonnlp.base import get_home_dir


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


# disabled since it takes a long time to download the model
@pytest.mark.serial
def _test_pretrained_big_text_models():
    text_models = ['big_rnn_lm_2048_512']
    pretrained_to_test = {'big_rnn_lm_2048_512': 'gbw'}

    for model_name in text_models:
        eprint('testing forward for %s' % model_name)
        pretrained_dataset = pretrained_to_test.get(model_name)
        model, _ = nlp.model.get_model(model_name, dataset_name=pretrained_dataset,
                                       pretrained=True)

        print(model)
        batch_size = 10
        hidden = model.begin_state(batch_size=batch_size, func=mx.nd.zeros)
        output, state = model(mx.nd.arange(330).reshape((33, 10)), hidden)
        output.wait_to_read()


@pytest.mark.serial
@pytest.mark.remote_required
def test_big_text_models(wikitext2_val_and_counter):
    # use a small vocabulary for testing
    val, val_freq = wikitext2_val_and_counter
    vocab = nlp.Vocab(val_freq)
    text_models = ['big_rnn_lm_2048_512']

    for model_name in text_models:
        eprint('testing forward for %s' % model_name)
        model, _ = nlp.model.get_model(model_name, vocab=vocab)

        print(model)
        model.collect_params().initialize()
        batch_size = 10
        hidden = model.begin_state(batch_size=batch_size, func=mx.nd.zeros)
        output, state = model(mx.nd.arange(330).reshape((33, 10)), hidden)
        output.wait_to_read()


@pytest.mark.serial
@pytest.mark.remote_required
@pytest.mark.parametrize('dropout_rate', [0.1, 0.0])
@pytest.mark.parametrize('model_dataset', [('transformer_en_de_512', 'WMT2014')])
def test_transformer_models(dropout_rate, model_dataset):
    model_name, pretrained_dataset = model_dataset
    src = mx.nd.ones((2, 10))
    tgt = mx.nd.ones((2, 8))
    valid_len = mx.nd.ones((2,))
    eprint('testing forward for %s, dropout rate %f' % (model_name, dropout_rate))
    with warnings.catch_warnings():  # TODO https://github.com/dmlc/gluon-nlp/issues/978
        warnings.simplefilter("ignore")
        model, _, _ = nlp.model.get_model(model_name, dataset_name=pretrained_dataset,
                                          pretrained=pretrained_dataset is not None,
                                          dropout=dropout_rate)

    print(model)
    if not pretrained_dataset:
        model.initialize()
    output, state = model(src, tgt, src_valid_length=valid_len, tgt_valid_length=valid_len)
    output.wait_to_read()
    del model
    mx.nd.waitall()


@pytest.mark.serial
@pytest.mark.remote_required
@pytest.mark.parametrize('wo_valid_len', [False, True])
def test_pretrained_roberta_models(wo_valid_len):
    models = ['roberta_12_768_12', 'roberta_24_1024_16']
    pretrained_datasets = ['openwebtext_ccnews_stories_books_cased']

    vocab_size = {'openwebtext_ccnews_stories_books_cased': 50265}
    special_tokens = ['<unk>', '<pad>', '<s>', '</s>', '<mask>']
    ones = mx.nd.ones((2, 10))
    valid_length = mx.nd.ones((2,))
    positions = mx.nd.zeros((2, 3))
    for model_name in models:
        for dataset in pretrained_datasets:
            eprint('testing forward for %s on %s' % (model_name, dataset))

            model, vocab = nlp.model.get_model(model_name, dataset_name=dataset,
                                               pretrained=True)
            assert len(vocab) == vocab_size[dataset]
            for token in special_tokens:
                assert token in vocab, "Token %s not found in the vocab" % token
            assert vocab['RandomWordByHaibin'] == vocab[vocab.unknown_token]
            assert vocab.padding_token == '<pad>'
            assert vocab.unknown_token == '<unk>'
            assert vocab.bos_token == '<s>'
            assert vocab.eos_token == '</s>'

            model.hybridize()
            if wo_valid_len:
                output = model(ones, masked_positions=positions)
            else:
                output = model(ones, valid_length, positions)
            output[0].wait_to_read()
            del model
            mx.nd.waitall()


@pytest.mark.serial
@pytest.mark.remote_required
@pytest.mark.parametrize('wo_valid_len', [False, True])
def test_pretrained_distilbert_models(wo_valid_len):
    models = ['distilbert_6_768_12']
    pretrained_datasets = ['distilbert_book_corpus_wiki_en_uncased']

    vocab_size = {'distilbert_book_corpus_wiki_en_uncased': 30522}
    special_tokens = ['[UNK]', '[PAD]', '[SEP]', '[CLS]', '[MASK]']
    ones = mx.nd.ones((2, 10))
    valid_length = mx.nd.ones((2,))
    for model_name in models:
        for dataset in pretrained_datasets:
            eprint('testing forward for %s on %s' % (model_name, dataset))

            model, vocab = nlp.model.get_model(model_name, dataset_name=dataset,
                                               pretrained=True,
                                               root='tests/data/model/')
            assert len(vocab) == vocab_size[dataset]
            for token in special_tokens:
                assert token in vocab, "Token %s not found in the vocab" % token
            assert vocab['RandomWordByHaibin'] == vocab[vocab.unknown_token]
            assert vocab.padding_token == '[PAD]'
            assert vocab.unknown_token == '[UNK]'

            model.hybridize()
            if wo_valid_len:
                output = model(ones)
            else:
                output = model(ones, valid_length)
            output[0].wait_to_read()
            del model
            mx.nd.waitall()

@pytest.mark.serial
@pytest.mark.remote_required
@pytest.mark.parametrize('disable_missing_parameters', [False, True])
def test_pretrained_bert_models(disable_missing_parameters):
    models = ['bert_12_768_12', 'bert_24_1024_16']
    pretrained = {
        'bert_12_768_12': [
            'book_corpus_wiki_en_cased', 'book_corpus_wiki_en_uncased', 'wiki_multilingual_uncased',
            'openwebtext_book_corpus_wiki_en_uncased', 'wiki_multilingual_cased', 'wiki_cn_cased', 'scibert_scivocab_uncased',
            'scibert_scivocab_cased', 'scibert_basevocab_uncased', 'scibert_basevocab_cased',
            'biobert_v1.0_pmc_cased', 'biobert_v1.0_pubmed_cased', 'biobert_v1.0_pubmed_pmc_cased',
            'biobert_v1.1_pubmed_cased', 'clinicalbert_uncased', 'kobert_news_wiki_ko_cased'
        ],
        'bert_24_1024_16': ['book_corpus_wiki_en_uncased', 'book_corpus_wiki_en_cased']
    }
    vocab_size = {'book_corpus_wiki_en_cased': 28996,
                  'book_corpus_wiki_en_uncased': 30522,
                  'openwebtext_book_corpus_wiki_en_uncased': 30522,
                  'wiki_multilingual_cased': 119547,
                  'wiki_cn_cased': 21128,
                  'wiki_multilingual_uncased': 105879,
                  'scibert_scivocab_uncased': 31090,
                  'scibert_scivocab_cased': 31116,
                  'scibert_basevocab_uncased': 30522,
                  'scibert_basevocab_cased': 28996,
                  'biobert_v1.0_pubmed_cased': 28996,
                  'biobert_v1.0_pmc_cased': 28996,
                  'biobert_v1.0_pubmed_pmc_cased': 28996,
                  'biobert_v1.1_pubmed_cased': 28996,
                  'clinicalbert_uncased': 30522,
                  'kobert_news_wiki_ko_cased': 8002}
    special_tokens = ['[UNK]', '[PAD]', '[SEP]', '[CLS]', '[MASK]']
    ones = mx.nd.ones((2, 10))
    valid_length = mx.nd.ones((2,))
    positions = mx.nd.zeros((2, 3))
    for model_name in models:
        pretrained_datasets = pretrained.get(model_name)
        for dataset in pretrained_datasets:
            has_missing_params = any(n in dataset for n in ('biobert', 'clinicalbert'))
            if not has_missing_params and disable_missing_parameters:
                # No parameters to disable for models pretrained on this dataset
                continue

            eprint('testing forward for %s on %s' % (model_name, dataset))

            if not has_missing_params:
                model, vocab = nlp.model.get_model(model_name, dataset_name=dataset,
                                                   pretrained=True)
            else:
                with pytest.raises(AssertionError):
                    model, vocab = nlp.model.get_model(model_name, dataset_name=dataset,
                                                       pretrained=True)

                if not disable_missing_parameters:
                    model, vocab = nlp.model.get_model(model_name, dataset_name=dataset,
                                                       pretrained=True,
                                                       pretrained_allow_missing=True)
                elif 'biobert' in dataset:
                    # Biobert specific test case
                    model, vocab = nlp.model.get_model(model_name, dataset_name=dataset,
                                                       pretrained=True,
                                                       pretrained_allow_missing=True,
                                                       use_decoder=False,
                                                       use_classifier=False)
                elif 'clinicalbert' in dataset:
                    # Clinicalbert specific test case
                    model, vocab = nlp.model.get_model(model_name, dataset_name=dataset,
                                                       pretrained=True,
                                                       pretrained_allow_missing=True,
                                                       use_decoder=False)
                else:
                    assert False, "Testcase needs to be adapted."

            assert len(vocab) == vocab_size[dataset]
            for token in special_tokens:
                assert token in vocab, "Token %s not found in the vocab" % token
            assert vocab['RandomWordByHaibin'] == vocab[vocab.unknown_token]
            assert vocab.padding_token == '[PAD]'
            assert vocab.unknown_token == '[UNK]'
            assert vocab.bos_token is None
            assert vocab.eos_token is None

            if has_missing_params and not disable_missing_parameters:
                with pytest.raises(RuntimeError):
                    output = model(ones, ones, valid_length, positions)
                    output[0].wait_to_read()
            else:
                output = model(ones, ones, valid_length, positions)
                output[0].wait_to_read()
            del model
            mx.nd.waitall()

@pytest.mark.serial
@pytest.mark.remote_required
@pytest.mark.parametrize('hparam_allow_override', [False, True])
def test_pretrained_bert_models_override(hparam_allow_override):
    models = ['bert_12_768_12', 'bert_24_1024_16',
              'roberta_12_768_12', 'roberta_24_1024_16']
    pretrained = {
        'bert_12_768_12':  ['book_corpus_wiki_en_uncased', 'book_corpus_wiki_en_cased'],
        'bert_24_1024_16': ['book_corpus_wiki_en_uncased', 'book_corpus_wiki_en_cased'],
        'roberta_12_768_12':  ['openwebtext_ccnews_stories_books_cased'],
        'roberta_24_1024_16': ['openwebtext_ccnews_stories_books_cased']
    }
    ones = mx.nd.ones((2, 10))
    valid_length = mx.nd.ones((2,))
    positions = mx.nd.zeros((2, 3))
    for model_name in models:
        pretrained_datasets = pretrained.get(model_name)
        for dataset in pretrained_datasets:
            eprint('testing forward for %s on %s' % (model_name, dataset))

            if hparam_allow_override:
                model, vocab = nlp.model.get_model(model_name, dataset_name=dataset,
                                                   pretrained=True,
                                                   root='tests/data/model/',
                                                   hparam_allow_override=hparam_allow_override,
                                                   ignore_extra=True,
                                                   num_layers=6)
            else:
                with pytest.raises(AssertionError):
                    model, vocab = nlp.model.get_model(model_name, dataset_name=dataset,
                                                       pretrained=True,
                                                       root='tests/data/model/',
                                                       num_layers=6)
                continue
            if 'roberta' in model_name:
                output = model(ones, valid_length, positions)
            else:
                output = model(ones, ones, valid_length, positions)
            output[0].wait_to_read()
            del model
            mx.nd.waitall()

@pytest.mark.serial
@pytest.mark.remote_required
@pytest.mark.parametrize('wo_valid_len', [False, True])
def test_bert_models(wo_valid_len):
    models = ['bert_12_768_12', 'bert_24_1024_16']
    layers = [12, 24]
    attention_heads = [12, 16]
    units = [768, 1024]
    dataset = 'book_corpus_wiki_en_uncased'
    vocab_size = 30522
    batch_size = 2
    seq_len = 3
    num_masks = 2
    ones = mx.nd.ones((batch_size, seq_len))
    valid_length = mx.nd.ones((batch_size, ))
    positions = mx.nd.ones((batch_size, num_masks))

    kwargs = [{'use_pooler': False, 'use_decoder': False, 'use_classifier': False},
              {'use_pooler': True, 'use_decoder': False, 'use_classifier': False},
              {'use_pooler': True, 'use_decoder': True, 'use_classifier': False},
              {'use_pooler': True, 'use_decoder': True, 'use_classifier': True},
              {'use_pooler': False, 'use_decoder': False, 'use_classifier': False,
               'output_attention': True},
              {'use_pooler': False, 'use_decoder': False, 'use_classifier': False,
               'output_attention': True, 'output_all_encodings': True},
              {'use_pooler': True, 'use_decoder': True, 'use_classifier': True,
               'output_attention': True, 'output_all_encodings': True}]

    def infer_shape(shapes, unit):
        inferred_shapes = []
        for shape in shapes:
            inferred_shape = list(shape)
            if inferred_shape[-1] == -1:
                inferred_shape[-1] = unit
            inferred_shapes.append(tuple(inferred_shape))
        return inferred_shapes

    def get_shapes(output):
        if not isinstance(output, (list, tuple)):
            return [output.shape]

        shapes = []
        for out in output:
            collect_shapes(out, shapes)

        return shapes

    def collect_shapes(item, shapes):
        if not isinstance(item, (list, tuple)):
            shapes.append(item.shape)
            return

        for child in item:
            collect_shapes(child, shapes)

    for model_name, layer, unit, head in zip(models, layers, units, attention_heads):
        eprint('testing forward for %s' % model_name)

        expected_shapes = [
            [(batch_size, seq_len, -1)],
            [(batch_size, seq_len, -1),
             (batch_size, -1)],
            [(batch_size, seq_len, -1),
             (batch_size, -1),
             (batch_size, num_masks, vocab_size)],
            [(batch_size, seq_len, -1),
             (batch_size, -1),
             (batch_size, 2),
             (batch_size, num_masks, vocab_size)],
            [(batch_size, seq_len, -1)] + [(batch_size, head, seq_len, seq_len)] * layer,
            [(batch_size, seq_len, -1)] * layer + [(batch_size, head, seq_len, seq_len)] * layer,
            [(batch_size, seq_len, -1)] * layer + [(batch_size, head, seq_len, seq_len)] * layer +
            [(batch_size, -1)] + [(batch_size, 2)] + [(batch_size, num_masks, vocab_size)],
        ]

        for kwarg, expected_shape in zip(kwargs, expected_shapes):
            eprint('testing forward for %s' % str(kwarg))
            expected_shape = infer_shape(expected_shape, unit)
            model, _ = nlp.model.get_model(model_name, dataset_name=dataset,
                                           pretrained=False, **kwarg)
            model.initialize()
            model.hybridize()

            if kwarg['use_decoder']:
                # position tensor is required for decoding
                if wo_valid_len:
                    output = model(ones, ones, masked_positions=positions)
                else:
                    output = model(ones, ones, valid_length, positions)
            else:
                if wo_valid_len:
                    output = model(ones, ones)
                else:
                    output = model(ones, ones, valid_length)

            out_shapes = get_shapes(output)
            assert out_shapes == expected_shape, (out_shapes, expected_shape)
            sync_instance = output[0] if not isinstance(output[0], list) else output[0][0]
            sync_instance.wait_to_read()
            del model
            mx.nd.waitall()


@pytest.mark.serial
@pytest.mark.remote_required
def test_language_models():
    text_models = ['standard_lstm_lm_200', 'standard_lstm_lm_650',
                   'standard_lstm_lm_1500', 'awd_lstm_lm_1150', 'awd_lstm_lm_600']
    pretrained_to_test = {'standard_lstm_lm_1500': 'wikitext-2',
                          'standard_lstm_lm_650': 'wikitext-2',
                          'standard_lstm_lm_200': 'wikitext-2',
                          'awd_lstm_lm_1150': 'wikitext-2',
                          'awd_lstm_lm_600': 'wikitext-2'}

    for model_name in text_models:
        eprint('testing forward for %s' % model_name)
        pretrained_dataset = pretrained_to_test.get(model_name)
        model, _ = nlp.model.get_model(model_name, dataset_name=pretrained_dataset,
                                       pretrained=pretrained_dataset is not None)

        print(model)
        if not pretrained_dataset:
            model.collect_params().initialize()
        output, state = model(mx.nd.arange(330).reshape(33, 10))
        output.wait_to_read()
        del model
        mx.nd.waitall()


@pytest.mark.serial
@pytest.mark.remote_required
def test_cache_models():
    cache_language_models = ['awd_lstm_lm_1150', 'awd_lstm_lm_600', 'standard_lstm_lm_200',
                             'standard_lstm_lm_650', 'standard_lstm_lm_1500']
    datasets = ['wikitext-2']
    for name in cache_language_models:
        for dataset_name in datasets:
            cache_cell = nlp.model.train.get_cache_model(name, dataset_name, window=1, theta=0.6,
                                                         lambdas=0.2)
            outs, word_history, cache_history, hidden = cache_cell(mx.nd.arange(
                10).reshape(10, 1), mx.nd.arange(10).reshape(10, 1), None, None)
            print(cache_cell)
            print("outs:")
            print(outs)
            print("word_history:")
            print(word_history)
            print("cache_history:")
            print(cache_history)


@pytest.mark.serial
@pytest.mark.remote_required
def test_get_cache_model_noncache_models():
    language_models_params = {
        'awd_lstm_lm_1150': 'awd_lstm_lm_1150_wikitext-2-f9562ed0.params',
        'awd_lstm_lm_600': 'awd_lstm_lm_600_wikitext-2-e952becc.params',
        'standard_lstm_lm_200': 'standard_lstm_lm_200_wikitext-2-b233c700.params',
        'standard_lstm_lm_650': 'standard_lstm_lm_650_wikitext-2-631f3904.params',
        'standard_lstm_lm_1500': 'standard_lstm_lm_1500_wikitext-2-a4163513.params'}
    datasets = ['wikitext-2']
    for name in language_models_params.keys():
        for dataset_name in datasets:
            _, vocab = nlp.model.get_model(name=name, dataset_name=dataset_name, pretrained=True)
            ntokens = len(vocab)

            cache_cell_0 = nlp.model.train.get_cache_model(name, dataset_name, window=1, theta=0.6,
                                                           lambdas=0.2)
            print(cache_cell_0)

            model, _ = nlp.model.get_model(name=name, dataset_name=dataset_name, pretrained=True)
            cache_cell_1 = nlp.model.train.CacheCell(
                model, ntokens, window=1, theta=0.6, lambdas=0.2)
            cache_cell_1.load_parameters(
                os.path.join(get_home_dir(), 'models', language_models_params.get(name)))
            print(cache_cell_1)

            outs0, word_history0, cache_history0, hidden0 = cache_cell_0(
                mx.nd.arange(10).reshape(10, 1), mx.nd.arange(10).reshape(10, 1), None, None)
            outs1, word_history1, cache_history1, hidden1 = cache_cell_1(
                mx.nd.arange(10).reshape(10, 1), mx.nd.arange(10).reshape(10, 1), None, None)

            assert outs0.shape == outs1.shape, outs0.shape
            assert len(word_history0) == len(word_history1), len(word_history0)
            assert len(cache_history0) == len(cache_history1), len(cache_history0)
            assert len(hidden0) == len(hidden1), len(hidden0)


@pytest.mark.serial
@pytest.mark.remote_required
def test_save_load_cache_models():
    cache_language_models = ['awd_lstm_lm_1150', 'awd_lstm_lm_600', 'standard_lstm_lm_200',
                             'standard_lstm_lm_650', 'standard_lstm_lm_1500']
    datasets = ['wikitext-2']
    for name in cache_language_models:
        for dataset_name in datasets:
            cache_cell = nlp.model.train.get_cache_model(name, dataset_name, window=1, theta=0.6,
                                                         lambdas=0.2)
            print(cache_cell)
            cache_cell.save_parameters(
                os.path.join(get_home_dir(), 'models', name + '-' + dataset_name + '.params'))
            cache_cell.load_parameters(
                os.path.join(get_home_dir(), 'models', name + '-' + dataset_name + '.params'))


@pytest.mark.serial
def test_save_load_big_rnn_models(tmp_path):
    ctx = mx.cpu()
    seq_len = 1
    batch_size = 1
    num_sampled = 6
    # network
    eval_model = nlp.model.language_model.BigRNN(10, 2, 3, 4, 5, 0.1, prefix='bigrnn')
    model = nlp.model.language_model.train.BigRNN(10, 2, 3, 4, 5, num_sampled, 0.1,
                                                  prefix='bigrnn')
    loss = mx.gluon.loss.SoftmaxCrossEntropyLoss()
    # verify param names
    model_params = sorted(model.collect_params().keys())
    eval_model_params = sorted(eval_model.collect_params().keys())
    for p0, p1 in zip(model_params, eval_model_params):
        assert p0 == p1, (p0, p1)
    model.initialize(mx.init.Xavier(), ctx=ctx)
    trainer = mx.gluon.Trainer(model.collect_params(), 'sgd')
    # prepare data, label and samples
    x = mx.nd.ones((seq_len, batch_size))
    y = mx.nd.ones((seq_len, batch_size))
    sampled_cls = mx.nd.ones((num_sampled,))
    sampled_cls_cnt = mx.nd.ones((num_sampled,))
    true_cls_cnt = mx.nd.ones((seq_len, batch_size))
    samples = (sampled_cls, sampled_cls_cnt, true_cls_cnt)
    hidden = model.begin_state(batch_size=batch_size, func=mx.nd.zeros, ctx=ctx)
    # test forward
    with mx.autograd.record():
        pred, hidden, new_y = model(x, y, hidden, samples)
        assert pred.shape == (seq_len, batch_size, 1 + num_sampled)
        assert new_y.shape == (seq_len, batch_size)
        pred = pred.reshape((-3, -1))
        new_y = new_y.reshape((-1,))
        l = loss(pred, new_y)
    l.backward()
    mx.nd.waitall()
    path = os.path.join(str(tmp_path), 'test_save_load_big_rnn_models.params')
    model.save_parameters(path)
    eval_model.load_parameters(path)


def test_big_rnn_model_share_params():
    ctx = mx.cpu()
    seq_len = 2
    batch_size = 1
    num_sampled = 6
    vocab_size = 10
    shape = (seq_len, batch_size)
    model = nlp.model.language_model.train.BigRNN(vocab_size, 2, 3, 4, 5, num_sampled, 0.1,
                                                  prefix='bigrnn', sparse_weight=False,
                                                  sparse_grad=False)
    loss = mx.gluon.loss.SoftmaxCrossEntropyLoss()
    model.hybridize()
    model.initialize(mx.init.Xavier(), ctx=ctx)
    trainer = mx.gluon.Trainer(model.collect_params(), 'sgd')
    batch_size = 1
    x = mx.nd.ones(shape)
    y = mx.nd.ones(shape)
    sampled_cls = mx.nd.ones((num_sampled,))
    sampled_cls_cnt = mx.nd.ones((num_sampled,))
    true_cls_cnt = mx.nd.ones(shape)
    samples = (sampled_cls, sampled_cls_cnt, true_cls_cnt)
    hidden = model.begin_state(batch_size=batch_size, func=mx.nd.zeros, ctx=ctx)
    with mx.autograd.record():
        pred, hidden, new_y = model(x, y, hidden, samples)
        assert pred.shape == (seq_len, batch_size, 1 + num_sampled)
        assert new_y.shape == (seq_len, batch_size)
        pred = pred.reshape((-3, -1))
        new_y = new_y.reshape((-1,))
        l = loss(pred, new_y)
    l.backward()
    assert model.decoder.weight._grad_stype == 'default'
    mx.nd.waitall()
    eval_model = nlp.model.language_model.BigRNN(vocab_size, 2, 3, 4, 5, 0.1, prefix='bigrnn',
                                                 params=model.collect_params())
    eval_model.hybridize()
    pred, hidden = eval_model(x, hidden)
    assert pred.shape == (seq_len, batch_size, vocab_size)
    mx.nd.waitall()


def test_weight_drop():
    class RefBiLSTM(gluon.Block):
        def __init__(self, size, **kwargs):
            super(RefBiLSTM, self).__init__(**kwargs)
            with self.name_scope():
                self._lstm_fwd = gluon.rnn.LSTM(size, bidirectional=False, prefix='l0')
                self._lstm_bwd = gluon.rnn.LSTM(size, bidirectional=False, prefix='r0')

        def forward(self, inpt):
            fwd = self._lstm_fwd(inpt)
            bwd_inpt = mx.nd.flip(inpt, 0)
            bwd = self._lstm_bwd(bwd_inpt)
            bwd = mx.nd.flip(bwd, 0)
            return mx.nd.concat(fwd, bwd, dim=2)
    net1 = RefBiLSTM(10)
    shared_net1 = RefBiLSTM(10, params=net1.collect_params())

    net2 = gluon.rnn.LSTM(10)
    shared_net2 = gluon.rnn.LSTM(10, params=net2.collect_params())

    net3 = gluon.nn.HybridSequential()
    net3.add(gluon.rnn.LSTM(10))
    shared_net3 = gluon.nn.HybridSequential(params=net3.collect_params())
    shared_net3.add(gluon.rnn.LSTM(10, params=net3[0].collect_params()))

    x = mx.random.uniform(shape=(3, 4, 5))
    nets = [(net1, shared_net1),
            (net2, shared_net2),
            (net3, shared_net3)]
    for net, shared_net in nets:
        net.initialize('uniform')
        mx.test_utils.assert_almost_equal(net(x).asnumpy(),
                                          shared_net(x).asnumpy())
        with mx.autograd.train_mode():
            mx.test_utils.assert_almost_equal(net(x).asnumpy(),
                                              shared_net(x).asnumpy())

        grads = {}
        with mx.autograd.record():
            y = net(x)
        y.backward()
        for name, param in net.collect_params().items():
            grads[name] = param.grad().copy()
        with mx.autograd.record():
            y = shared_net(x)
        y.backward()
        for name, param in shared_net.collect_params().items():
            mx.test_utils.assert_almost_equal(grads[name].asnumpy(), param.grad().asnumpy())

        drop_rate = 0.5
        nlp.model.utils.apply_weight_drop(net, '.*h2h_weight', drop_rate)

        with mx.autograd.predict_mode():
            mx.test_utils.assert_almost_equal(net(x).asnumpy(),
                                              shared_net(x).asnumpy())
        with mx.autograd.train_mode():
            assert not mx.test_utils.almost_equal(net(x).asnumpy(),
                                                  shared_net(x).asnumpy())

        grads = {}
        with mx.autograd.record():
            y = net(x)
        y.backward()
        for name, param in net.collect_params().items():
            grads[name] = param.grad().copy()
        with mx.autograd.record():
            y = shared_net(x)
        y.backward()
        for name, param in shared_net.collect_params().items():
            assert not mx.test_utils.almost_equal(grads[name].asnumpy(), param.grad().asnumpy())


# helper method used by test_hparam_allow_override_parameter_in_get_model_api
def verify_get_model_with_hparam_allow_override(models, hparam_allow_override, predefined_args_dict,
        mutable_args, dataset_name):

    for model in models:
        predefined_args = predefined_args_dict[model].copy()
        if hparam_allow_override:
            params_that_should_throw_exception = set()
        else:
            params_that_should_throw_exception = set(predefined_args.keys()) - set(mutable_args)
        params_that_threw_exception = set()
        for param in predefined_args:
            try:
                nlp.model.get_model(model, dataset_name=dataset_name,
                    hparam_allow_override=hparam_allow_override, **{param: predefined_args[param]})
            except:
                # we're expecting get_model to fail if hparam_allow_override is False
                # and the parameter is not in the set of mutable parameters
                expected = not hparam_allow_override and not param in mutable_args
                assert expected, 'Unexpected exception when creating model ' + model + ' with '\
                       'parameter ' + param + '.\n'
                params_that_threw_exception.add(param)

        assert params_that_threw_exception == params_that_should_throw_exception


@pytest.mark.parametrize('hparam_allow_override', [False, True])
def test_hparam_allow_override_parameter_in_get_model_api(hparam_allow_override):
    models = ['awd_lstm_lm_1150', 'awd_lstm_lm_600']
    mutable_args_of_models = ['dropout', 'weight_drop', 'drop_h', 'drop_i', 'drop_e']
    predefined_args_dict = nlp.model.language_model.awd_lstm_lm_hparams.copy()
    verify_get_model_with_hparam_allow_override(models, hparam_allow_override, predefined_args_dict,
            mutable_args_of_models, 'wikitext-2')

    models = ['standard_lstm_lm_200', 'standard_lstm_lm_650', 'standard_lstm_lm_1500']
    mutable_args_of_models = ['dropout']
    predefined_args_dict = nlp.model.language_model.standard_lstm_lm_hparams.copy()
    verify_get_model_with_hparam_allow_override(models, hparam_allow_override, predefined_args_dict,
            mutable_args_of_models, 'wikitext-2')

    models = ['big_rnn_lm_2048_512']
    mutable_args_of_models = ['embed_dropout', 'encode_dropout']
    predefined_args_dict = nlp.model.language_model.big_rnn_lm_hparams.copy()
    verify_get_model_with_hparam_allow_override(models, hparam_allow_override, predefined_args_dict,
            mutable_args_of_models, 'wikitext-2')

    models = ['transformer_en_de_512']
    mutable_args_of_models = ['num_units', 'hidden_size', 'dropout', 'epsilon', 'num_layers',
                                  'num_heads', 'scaled']
    predefined_args_dict = {
        'transformer_en_de_512': nlp.model.transformer.transformer_en_de_hparams.copy()
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        verify_get_model_with_hparam_allow_override(models, hparam_allow_override, predefined_args_dict,
            mutable_args_of_models, 'WMT2014')

    models = ['distilbert_6_768_12']
    mutable_args_of_models = ['use_residual', 'dropout', 'word_embed']
    predefined_args_dict = nlp.model.bert.bert_hparams.copy()
    verify_get_model_with_hparam_allow_override(models, hparam_allow_override, predefined_args_dict,
            mutable_args_of_models, 'distilbert_book_corpus_wiki_en_uncased')


def test_gelu():
    x = mx.random.uniform(shape=(3, 4, 5))
    net = nlp.model.GELU()
    y = net(x)
    assert y.shape == x.shape
    y.wait_to_read()


def test_transformer_encoder():
    batch_size = 2
    seq_length = 5
    units = 768
    inputs = mx.random.uniform(shape=(batch_size, seq_length, units))
    mask = mx.nd.ones([batch_size, seq_length, seq_length])
    cell = nlp.model.TransformerEncoderCell(units=768, hidden_size=3072, num_heads=12,
                                            attention_cell='multi_head', dropout=0.0,
                                            use_residual=True, scaled=True,
                                            output_attention=False,
                                            prefix='transformer_cell')
    cell.collect_params().initialize()
    cell.hybridize()
    outputs, attention_weights = cell(inputs, mask)
    outputs.wait_to_read()
    mx.nd.waitall()
    assert outputs.shape == (batch_size, seq_length, units)
