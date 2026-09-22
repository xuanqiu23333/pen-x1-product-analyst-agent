from app.schemas.models import Evidence, Fact
from app.schemas.state import AnalysisState
from app.skills.report_generation import run_report_generation


def test_real_report_is_evidence_bound_smoke_report_with_limitations():
    state = AnalysisState(
        project={'mode': 'REAL_MODE', 'data_provider_status': {}},
        facts=[
            Fact(id='battery_configurations', category='project', name='battery',
                 value=['14500','AA','AAA','2AA','2AAA']),
            Fact(id='target_price_usd', category='project', name='price', value=34.95),
        ],
        evidence=[Evidence(id='ev-review-R1', source='Apify', content='clip issue',
                           data_nature='IMPORTED_DATA', source_type='APIFY_REAL')],
        voc={
            'status':'COMPLETED','review_count':26,'coverage_level':'PARTIAL',
            'source_counts':{'APIFY_REAL':26},
            'product_review_counts':{'Streamlight MicroStream':13,'Nitecore MT2A Pro':13},
            'rating_distribution':{'Streamlight MicroStream':{'5':10,'4':3}},
                'pain_points':[{'pain_point':'夹子固定性','mention_count':1,'sample_size':26,
                                'mention_rate':0.0385,'evidence_review_ids':['ev-review-R1']}],
                'canonical_pain_points':[{
                    'canonical_pain_point':'夹具拆装可能损伤表面','aspect':'clip','mentions':1,
                    'product_sample_size':13,'product_mention_rate':0.0769,
                    'corpus_sample_size':26,'corpus_mention_rate':0.0385,
                    'sample_size':26,'mention_rate':0.0385,'products':['Streamlight MicroStream'],
                    'product_distribution':{'Streamlight MicroStream':{
                        'mentions':1,'sample_size':13,'mention_rate':0.0769}},
                    'raw_pain_points':['夹子固定性'],'evidence_ids':['ev-review-R1'],
                    'confidence':'LOW','cross_product_support':False,
                }],
                'product_insights':{'Streamlight MicroStream':{'pain_points':[
                    {'pain_point':'not 24 hours','mention_count':1,'sample_size':13,
                     'evidence_review_ids':['ev-review-R1']}] }},
                'positive_feedback':[],
        },
        opportunities=[{'title':'夹子结构验证机会','supporting_reviews':1,
                        'canonical_pain_points':['夹具拆装可能损伤表面'],
                        'evidence_ids':['ev-review-R1'],'confidence':'LOW'}],
    )

    report = run_report_generation(state, mode='REAL')

    assert report['title'] == 'PEN-X1 Real VOC Smoke Report'
    for heading in ('Data Coverage','Product Review Counts','Rating Distribution',
                    'Canonical Pain Points','Positive Signals','Purchase Drivers','Cross-product Comparison',
                    'Market Opportunities','Evidence References','Data Limitations'):
        assert heading in report['markdown']
    assert '不代表 Amazon 全量消费者意见' in report['markdown']
    assert '产品机会识别及系统验证' in report['markdown']
    assert '最高频痛点 not 24 hours 1/13 条；Evidence：ev-review-R1' in report['markdown']
    assert 'Canonical Pain Points' in report['markdown']
    assert '夹具拆装可能损伤表面' in report['markdown']
    assert '原始表述：夹子固定性' in report['markdown']
    assert '| Pain Point | Mentions | Product Rate | Corpus Rate | Affected Products | Evidence Count |' in report['markdown']
    assert '7.69% of Streamlight MicroStream reviews' in report['markdown']
    assert '3.85% of all REAL reviews' in report['markdown']
    assert 'UNKNOWN / NEED_VERIFY' in report['markdown']
