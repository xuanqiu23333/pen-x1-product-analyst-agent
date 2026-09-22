"""Deterministic aggregation for already-extracted semantic pain points."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict


FAMILIES = {
    'battery_runtime': ('runtime', '电池续航有限'),
    'battery_compatibility': ('battery', '电池类型影响输出能力'),
    'charging': ('charging', '充电方式不便'),
    'thermal': ('heat', '高亮或持续开启时发热'),
    'switch_activation': ('switch', '开关敏感导致误触开启'),
    'switch_usability': ('switch', '开关操作便利性不足'),
    'beam': ('beam', '光束形态与调焦受限'),
    'size': ('size', '尺寸影响便携与操作'),
    'clip_finish': ('clip', '夹具拆装可能损伤表面'),
    'tail_stand': ('other', '尾盖站立稳定性不足'),
    'brightness_value': ('brightness', '亮度与价格预期不匹配'),
    'modes': ('modes', '亮度档位灵活性不足'),
}


def _normalized(value: str) -> str:
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', value).strip().lower())


def _has(text: str, *signals: str) -> bool:
    return any(signal in text for signal in signals)


def _family(point: dict) -> tuple[str, str, str]:
    aspect = str(point.get('aspect') or 'other').lower()
    wording = str(point.get('pain_point') or point.get('topic') or '').strip()
    text = _normalized(wording)

    if aspect == 'charging' or _has(text, 'charging port', 'external charging', '取出电池充电', '充电口'):
        key = 'charging'
    elif aspect == 'heat' or _has(text, 'overheat', 'gets hot', 'gets really warm', 'due to heat', '发热', '变得很热', '热量'):
        key = 'thermal'
    elif aspect == 'beam' or _has(text, 'beam', 'focus', 'flood', 'spot', '调焦', '聚光', '泛光'):
        key = 'beam'
    elif aspect == 'clip' and _has(text, 'scratch', 'paint', 'finish', '划伤', '掉漆', '表面'):
        key = 'clip_finish'
    elif _has(text, 'tail cap stand', 'tail-standing', 'tail standing', '站立', '尾盖') and aspect in {'other', 'switch'}:
        key = 'tail_stand' if aspect == 'other' else 'switch_usability'
    elif aspect == 'switch' and _has(text, 'sensitive', 'accidental', 'inadvertent', 'turn on in pocket', '误触', '意外开启'):
        key = 'switch_activation'
    elif aspect == 'switch':
        key = 'switch_usability'
    elif aspect == 'size' or _has(text, 'too big', 'larger', 'wider', 'conceal', 'hold in your mouth', '尺寸', '便携'):
        key = 'size'
    elif aspect == 'modes' or _has(text, 'one brightness level', 'brightness mode', '亮度档位'):
        key = 'modes'
    elif (_has(text, 'alkaline', 'non-rechargeable', '非充电碱性电池', 'battery type', '电池类型')
          and _has(text, 'maximum brightness', '最大亮度', 'output', '输出')):
        key = 'battery_compatibility'
    elif aspect == 'runtime' or _has(text, 'run time', 'runtime', 'battery life', 'only lasts', '续航'):
        key = 'battery_runtime'
    elif aspect in {'brightness', 'price'} or _has(text, 'not as bright', 'lumen', '流明', '性价比', '价位'):
        key = 'brightness_value'
    else:
        # Unknown concepts stay distinct. The aspect is part of the key only to
        # prevent accidental merging; it never forces two wordings together.
        return f'raw:{aspect}:{text}', aspect, wording

    canonical_aspect, label = FAMILIES[key]
    if key == 'battery_runtime' and _has(text, 'single aaa', '单 aaa', '单节 aaa'):
        label = '单节 AAA 电池续航有限'
    return key, canonical_aspect, label


def canonicalize_pain_points(
        points: list[dict], sample_size: int,
        product_sample_sizes: dict[str, int] | None = None,
        evidence_product_map: dict[str, str] | None = None) -> list[dict]:
    """Merge equivalent problems while counting each review Evidence once."""
    product_sample_sizes = product_sample_sizes or {}
    evidence_product_map = evidence_product_map or {}
    groups: dict[str, dict] = defaultdict(lambda: {
        'aspect': 'other', 'label': '', 'raw': [], 'evidence': [], 'products': [],
        'product_evidence': defaultdict(list),
    })
    for point in points:
        wording = str(point.get('pain_point') or point.get('topic') or '').strip()
        if not wording:
            continue
        key, aspect, label = _family(point)
        group = groups[key]
        group['aspect'] = aspect
        group['label'] = label
        if wording not in group['raw']:
            group['raw'].append(wording)
        evidence_ids = point.get('evidence_review_ids') or point.get('evidence_ids') or []
        for evidence_id in evidence_ids:
            if evidence_id not in group['evidence']:
                group['evidence'].append(evidence_id)
        products = (point.get('affected_products') or point.get('products')
                    or list((point.get('product_distribution') or {}).keys()))
        for product in products:
            if product not in group['products']:
                group['products'].append(product)
        for evidence_id in evidence_ids:
            product = evidence_product_map.get(evidence_id)
            if product is None and len(products) == 1:
                product = products[0]
            if product and evidence_id not in group['product_evidence'][product]:
                group['product_evidence'][product].append(evidence_id)

    results = []
    for group in groups.values():
        mentions = len(group['evidence'])
        label = group['label']
        if group['aspect'] == 'runtime' and any(
                _has(_normalized(raw), 'single aaa', '单 aaa', '单节 aaa') for raw in group['raw']):
            label = '单节 AAA 电池续航有限'
        products = sorted(group['products'])
        corpus_rate = round(mentions / sample_size, 4) if sample_size else 0
        product_distribution = {}
        for product in products:
            product_mentions = len(group['product_evidence'].get(product, []))
            product_size = int(product_sample_sizes.get(
                product, sample_size if len(products) == 1 else 0) or 0)
            product_distribution[product] = {
                'mentions': product_mentions,
                'sample_size': product_size,
                'mention_rate': round(product_mentions / product_size, 4) if product_size else 0,
            }
        product_sample_size = sum(item['sample_size'] for item in product_distribution.values())
        product_rate = round(mentions / product_sample_size, 4) if product_sample_size else 0
        results.append({
            'canonical_pain_point': label,
            'aspect': group['aspect'],
            'mentions': mentions,
            'product_sample_size': product_sample_size,
            'product_mention_rate': product_rate,
            'corpus_sample_size': sample_size,
            'corpus_mention_rate': corpus_rate,
            'sample_size': sample_size,
            'mention_rate': corpus_rate,
            'frequency': corpus_rate,
            'products': products,
            'product_distribution': product_distribution,
            'raw_pain_points': group['raw'],
            'evidence_ids': group['evidence'],
            'confidence': 'MEDIUM' if mentions >= 2 else 'LOW',
            'cross_product_support': len(products) >= 2,
        })
    return sorted(results, key=lambda item: (-item['mentions'], item['aspect'], item['canonical_pain_point']))
