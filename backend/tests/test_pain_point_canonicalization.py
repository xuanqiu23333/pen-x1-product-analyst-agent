from importlib import import_module

import pytest


def canonicalize(points: list[dict], sample_size: int,
                 product_sample_sizes: dict[str, int] | None = None,
                 evidence_product_map: dict[str, str] | None = None) -> list[dict]:
    try:
        module = import_module('app.services.pain_point_canonicalizer')
    except ModuleNotFoundError:
        pytest.fail('canonical pain point service is not implemented')
    return module.canonicalize_pain_points(
        points, sample_size=sample_size,
        product_sample_sizes=product_sample_sizes,
        evidence_product_map=evidence_product_map,
    )


def point(aspect: str, wording: str, evidence_ids: list[str], products: list[str]) -> dict:
    return {
        'aspect': aspect,
        'pain_point': wording,
        'evidence_review_ids': evidence_ids,
        'affected_products': products,
    }


def test_runtime_wordings_merge_and_count_unique_review_evidence():
    result = canonicalize([
        point('runtime', 'not going to give 24 hours of run time', ['ev-review-R1'], ['Streamlight']),
        point('runtime', 'only lasts about an hour and a half on a single AAA battery',
              ['ev-review-R1', 'ev-review-R2'], ['Streamlight']),
        point('battery', 'single AAA battery gives limited battery life',
              ['ev-review-R2'], ['Streamlight']),
    ], sample_size=26, product_sample_sizes={'Streamlight': 13},
       evidence_product_map={'ev-review-R1':'Streamlight', 'ev-review-R2':'Streamlight'})

    assert result == [{
        'canonical_pain_point': '单节 AAA 电池续航有限',
        'aspect': 'runtime',
        'mentions': 2,
        'product_sample_size': 13,
        'product_mention_rate': 0.1538,
        'corpus_sample_size': 26,
        'corpus_mention_rate': 0.0769,
        'sample_size': 26,
        'mention_rate': 0.0769,
        'frequency': 0.0769,
        'products': ['Streamlight'],
        'product_distribution': {
            'Streamlight': {'mentions': 2, 'sample_size': 13, 'mention_rate': 0.1538},
        },
        'raw_pain_points': [
            'not going to give 24 hours of run time',
            'only lasts about an hour and a half on a single AAA battery',
            'single AAA battery gives limited battery life',
        ],
        'evidence_ids': ['ev-review-R1', 'ev-review-R2'],
        'confidence': 'MEDIUM',
        'cross_product_support': False,
    }]


def test_battery_runtime_and_battery_compatibility_remain_separate():
    result = canonicalize([
        point('runtime', 'battery life is short', ['ev-review-R1'], ['A']),
        point('battery', 'alkaline battery cannot reach maximum brightness', ['ev-review-R2'], ['B']),
    ], sample_size=10)

    assert [item['aspect'] for item in result] == ['battery', 'runtime']
    assert {item['canonical_pain_point'] for item in result} == {
        '电池类型影响输出能力', '电池续航有限',
    }


def test_battery_compatibility_signal_overrides_upstream_brightness_aspect():
    result = canonicalize([
        point('brightness', '使用非充电碱性电池时无法达到最大亮度',
              ['ev-review-R1'], ['Nitecore']),
        point('brightness', '在这个价位段流明较低，性价比不足',
              ['ev-review-R2'], ['Streamlight']),
    ], sample_size=26)

    assert {item['canonical_pain_point'] for item in result} == {
        '电池类型影响输出能力', '亮度与价格预期不匹配',
    }


def test_thermal_wordings_merge_without_losing_traceability():
    result = canonicalize([
        point('heat', 'gets hot at full brightness',
              ['ev-review-R1', 'ev-review-R1', 'ev-review-R2'], ['Nitecore']),
        point('heat', 'lens deformed due to heat',
              ['ev-review-R3', 'ev-review-R4'], ['Nitecore']),
    ], sample_size=26, product_sample_sizes={'Nitecore':13},
       evidence_product_map={f'ev-review-R{i}':'Nitecore' for i in range(1, 5)})

    assert len(result) == 1
    assert result[0]['canonical_pain_point'] == '高亮或持续开启时发热'
    assert result[0]['mentions'] == 4
    assert result[0]['raw_pain_points'] == [
        'gets hot at full brightness', 'lens deformed due to heat',
    ]
    assert result[0]['evidence_ids'] == [
        'ev-review-R1', 'ev-review-R2', 'ev-review-R3', 'ev-review-R4',
    ]
    assert result[0]['product_sample_size'] == 13
    assert result[0]['product_mention_rate'] == 0.3077
    assert result[0]['corpus_sample_size'] == 26
    assert result[0]['corpus_mention_rate'] == 0.1538
    assert result[0]['product_distribution']['Nitecore'] == {
        'mentions':4, 'sample_size':13, 'mention_rate':0.3077,
    }
    assert result[0]['confidence'] == 'MEDIUM'


def test_cross_product_distribution_uses_each_products_own_denominator():
    result = canonicalize([
        point('brightness', 'not bright enough', ['ev-review-N1', 'ev-review-N2'], ['Nitecore']),
        point('brightness', 'low lumen for price',
              ['ev-review-S1', 'ev-review-S2', 'ev-review-S3'], ['Streamlight']),
    ], sample_size=26,
       product_sample_sizes={'Nitecore':13, 'Streamlight':13},
       evidence_product_map={
           'ev-review-N1':'Nitecore', 'ev-review-N2':'Nitecore',
           'ev-review-S1':'Streamlight', 'ev-review-S2':'Streamlight',
           'ev-review-S3':'Streamlight',
       })

    item = result[0]
    assert item['mentions'] == 5
    assert item['product_sample_size'] == 26
    assert item['product_mention_rate'] == 0.1923
    assert item['corpus_mention_rate'] == 0.1923
    assert item['product_distribution'] == {
        'Nitecore': {'mentions':2, 'sample_size':13, 'mention_rate':0.1538},
        'Streamlight': {'mentions':3, 'sample_size':13, 'mention_rate':0.2308},
    }
    assert sum(row['mentions'] for row in item['product_distribution'].values()) == item['mentions']


def test_unknown_unrelated_wordings_are_not_merged_by_shared_aspect():
    result = canonicalize([
        point('other', 'lanyard hole is too small', ['ev-review-R1'], ['A']),
        point('other', 'packaging arrived damaged', ['ev-review-R2'], ['A']),
    ], sample_size=10)

    assert len(result) == 2
    assert all(item['mentions'] == 1 and item['confidence'] == 'LOW' for item in result)
