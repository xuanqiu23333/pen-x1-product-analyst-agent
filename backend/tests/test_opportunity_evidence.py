from app.schemas.models import Evidence, Fact
from app.schemas.state import AnalysisState
from app.skills.opportunity_analysis import run_opportunity_analysis

def test_opportunity_requires_four_evidence_classes_and_uses_fact_ids():
    state = AnalysisState(
      facts=[Fact(id='battery_configurations', category='project', name='battery configurations', value=['14500','AA'], data_nature='FACT')],
      evidence=[Evidence(id='ev-review-r1', source='csv', content='battery concern', data_nature='SAMPLE'), Evidence(id='ev-competitor-a', source='fixture', content='single battery family', data_nature='PUBLIC_FIXTURE'), Evidence(id='ev-market-1', source='fixture', content='market pattern', data_nature='PUBLIC_FIXTURE')],
      voc={'review_count':26,'pain_points':[{'aspect':'battery','pain_point':'电池适配与可获得性',
           'mention_count':4,'mention_rate':0.1538,'product_distribution':{'A':2,'B':2},
           'evidence_review_ids':['ev-review-r1']}]},
      competitors=[{'limitations':['single battery family']}], market={'research':{'sources':[{'status':'PUBLIC_FIXTURE'}]}}
    )
    result = run_opportunity_analysis(state)
    assert result[0]['product_fact_ids'] == ['battery_configurations']
    assert result[0]['voc_evidence'] == ['ev-review-r1']
    assert result[0]['competitor_evidence'] == ['ev-competitor-a']
    assert result[0]['status'] == 'INFERRED'
    assert result[0]['source_pain_points'] == ['电池适配与可获得性']
    assert result[0]['supporting_reviews'] == 1
    assert result[0]['evidence_ids'] == ['ev-review-r1']
    assert result[0]['affected_products'] == ['A', 'B']
    assert result[0]['opportunity'] == result[0]['title']
    assert result[0]['confidence'] != 'HIGH'


def test_real_opportunities_use_canonical_points_once_and_bind_canonical_name():
    state = AnalysisState(
        facts=[Fact(id='battery_configurations', category='project', name='battery configurations',
                    value=['14500', 'AA', 'AAA', '2AA', '2AAA'], data_nature='FACT')],
        evidence=[
            Evidence(id='ev-review-R1', source='Apify', content='short runtime',
                     data_nature='IMPORTED_DATA', source_type='APIFY_REAL'),
            Evidence(id='ev-review-R2', source='Apify', content='short battery life',
                     data_nature='IMPORTED_DATA', source_type='APIFY_REAL'),
        ],
        voc={
            'review_count': 26,
            'pain_points': [
                {'aspect':'runtime', 'pain_point':'short runtime', 'evidence_review_ids':['ev-review-R1']},
                {'aspect':'battery', 'pain_point':'short battery life', 'evidence_review_ids':['ev-review-R2']},
            ],
            'canonical_pain_points': [{
                'canonical_pain_point':'电池续航有限', 'aspect':'runtime', 'mentions':2,
                'product_sample_size':13, 'product_mention_rate':0.1538,
                'corpus_sample_size':26, 'corpus_mention_rate':0.0769,
                'sample_size':26, 'mention_rate':0.0769, 'products':['A'],
                'product_distribution':{'A':{'mentions':2,'sample_size':13,'mention_rate':0.1538}},
                'raw_pain_points':['short runtime', 'short battery life'],
                'evidence_ids':['ev-review-R1', 'ev-review-R2'], 'confidence':'MEDIUM',
                'cross_product_support':False,
            }],
        },
    )

    result = run_opportunity_analysis(state, mode='REAL')

    assert len(result) == 1
    assert result[0]['canonical_pain_points'] == ['电池续航有限']
    assert result[0]['source_pain_points'] == ['short runtime', 'short battery life']
    assert result[0]['evidence_ids'] == ['ev-review-R1', 'ev-review-R2']
    assert result[0]['supporting_reviews'] == 2
    assert result[0]['confidence'] == 'MEDIUM'
    assert result[0]['cross_product_support'] is False
    assert result[0]['mention_frequency'] == 0.1538
    assert result[0]['product_mention_rate'] == 0.1538
    assert result[0]['corpus_mention_rate'] == 0.0769
    assert result[0]['product_capability'].endswith('NEED_VERIFY')


def test_price_relevance_uses_product_fact_value_instead_of_fixed_number():
    state = AnalysisState(
        facts=[Fact(id='target_price_usd', category='project', name='target price',
                    value=39.95, unit='USD', data_nature='FACT')],
        evidence=[Evidence(id='ev-review-R1', source='Apify', content='poor value',
                           data_nature='IMPORTED_DATA', source_type='APIFY_REAL')],
        voc={'review_count':1, 'canonical_pain_points':[{
            'canonical_pain_point':'亮度与价格预期不匹配', 'aspect':'brightness',
            'mentions':1, 'sample_size':1, 'mention_rate':1.0, 'products':['A'],
            'product_sample_size':1, 'product_mention_rate':1.0,
            'corpus_sample_size':1, 'corpus_mention_rate':1.0,
            'product_distribution':{'A':{'mentions':1,'sample_size':1,'mention_rate':1.0}},
            'raw_pain_points':['poor value'], 'evidence_ids':['ev-review-R1'],
            'confidence':'LOW', 'cross_product_support':False,
        }]},
    )

    result = run_opportunity_analysis(state, mode='REAL')

    assert '$39.95' in result[0]['product_capability']
    assert '$34.95' not in result[0]['product_capability']
