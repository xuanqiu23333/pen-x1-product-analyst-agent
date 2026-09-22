from app.schemas.models import Claim, Evidence
from app.schemas.state import AnalysisState
from app.services.decision_engine import DecisionEngine
from app.validators.report_validator import validate_claims, validate_report

def test_sample_market_and_open_technical_risk_produce_partial_and_conditional_go():
    state=AnalysisState(market={'research':{'sources':[{'status':'PUBLIC_FIXTURE'}]}}, voc={'review_count':3}, technical_risks=[{'severity':5,'status':'NEED_VERIFY','mitigation':'test'}], profit_analysis={'cost_status':{'fba':'UNKNOWN'}})
    decision=DecisionEngine().evaluate(state)
    assert decision['gates'][0]['status'] == 'PARTIAL'
    assert decision['decision'] == 'CONDITIONAL_GO'

def test_claim_without_fact_or_evidence_is_unsupported():
    result=validate_claims(AnalysisState(), [Claim(claim_id='c1', text='PEN-X1 具有 1000 流明输出', claim_type='product_spec', fact_ids=[], evidence_ids=[], status='UNSUPPORTED')])
    assert result.errors

def test_real_voc_validator_rejects_missing_evidence_and_bad_percentages():
    state=AnalysisState(
        project={'mode':'REAL_MODE'},
        evidence=[Evidence(id='ev-review-R1',source='Apify',content='real',
                           data_nature='IMPORTED_DATA',source_type='APIFY_REAL')],
        voc={'review_count':1,'coverage_level':'LOW_COVERAGE','status':'COMPLETED',
             'source_counts':{'APIFY_REAL':1},'pain_points':[{
                 'pain_point':'问题','mention_count':2,'sample_size':1,'mention_rate':0.2,
                 'evidence_review_ids':['ev-review-MISSING']}]} ,
        report={'markdown':'PEN-X1 流明、续航、防护等级、热管理、尺寸、重量、认证均为 UNKNOWN / NEED_VERIFY。'}
    )
    result=validate_report(state)
    assert result.status == 'FAIL'
    assert any('Evidence' in item or '提及数' in item for item in result.errors)

def test_partial_real_voc_with_traceable_evidence_is_warn_not_fail():
    state=AnalysisState(
        project={'mode':'REAL_MODE'},
        evidence=[Evidence(id='ev-review-R1',source='Apify',content='real',
                           data_nature='IMPORTED_DATA',source_type='APIFY_REAL')],
        voc={'review_count':1,'coverage_level':'LOW_COVERAGE','status':'COMPLETED',
             'source_counts':{'APIFY_REAL':1},'pain_points':[{
                 'pain_point':'问题','mention_count':1,'sample_size':1,'mention_rate':1.0,
                 'evidence_review_ids':['ev-review-R1']}]} ,
        report={'markdown':'PEN-X1 流明、续航、防护等级、热管理、尺寸、重量、认证均为 UNKNOWN / NEED_VERIFY。'}
    )
    result=validate_report(state)
    assert result.status == 'WARN'
    assert result.errors == []


def test_real_validator_rejects_invalid_canonical_counts_and_unbound_opportunity():
    state = AnalysisState(
        project={'mode':'REAL_MODE'},
        evidence=[Evidence(id='ev-review-R1', source='Apify', content='real',
                           data_nature='IMPORTED_DATA', source_type='APIFY_REAL')],
        voc={
            'review_count':1, 'coverage_level':'LOW_COVERAGE', 'status':'COMPLETED',
            'source_counts':{'APIFY_REAL':1, 'SAMPLE':0}, 'pain_points':[],
            'canonical_pain_points':[{
                'canonical_pain_point':'续航有限', 'aspect':'runtime', 'mentions':2,
                'sample_size':1, 'mention_rate':2.0, 'products':['A'],
                'raw_pain_points':[], 'evidence_ids':['ev-review-R1', 'ev-review-R1'],
                'confidence':'MEDIUM',
            }],
        },
        opportunities=[{'title':'续航机会', 'evidence_ids':['ev-review-R1']}],
        report={'markdown':'所有未知参数均为 UNKNOWN / NEED_VERIFY。'},
    )

    result = validate_report(state)

    assert result.status == 'FAIL'
    assert any('Canonical Pain Point' in item and '唯一 Evidence' in item for item in result.errors)
    assert any('raw_pain_points' in item for item in result.errors)
    assert any('未绑定 canonical pain point' in item for item in result.errors)


def test_real_validator_rejects_duplicate_opportunities_for_one_canonical_problem():
    canonical = {
        'canonical_pain_point':'续航有限', 'aspect':'runtime', 'mentions':1,
        'sample_size':1, 'mention_rate':1.0, 'products':['A'],
        'raw_pain_points':['short runtime'], 'evidence_ids':['ev-review-R1'],
        'confidence':'LOW',
    }
    state = AnalysisState(
        project={'mode':'REAL_MODE'},
        evidence=[Evidence(id='ev-review-R1', source='Apify', content='real',
                           data_nature='IMPORTED_DATA', source_type='APIFY_REAL')],
        voc={'review_count':1, 'coverage_level':'LOW_COVERAGE', 'status':'COMPLETED',
             'source_counts':{'APIFY_REAL':1, 'SAMPLE':0}, 'pain_points':[],
             'canonical_pain_points':[canonical]},
        opportunities=[
            {'title':'机会一', 'canonical_pain_points':['续航有限'], 'evidence_ids':['ev-review-R1']},
            {'title':'机会二', 'canonical_pain_points':['续航有限'], 'evidence_ids':['ev-review-R1']},
        ],
        report={'markdown':'所有未知参数均为 UNKNOWN / NEED_VERIFY。'},
    )

    result = validate_report(state)

    assert result.status == 'FAIL'
    assert any('重复生成多个 Market Opportunity' in item for item in result.errors)


def test_real_validator_requires_opportunity_evidence_to_belong_to_bound_canonical():
    state = AnalysisState(
        project={'mode':'REAL_MODE'},
        evidence=[
            Evidence(id='ev-review-R1', source='Apify', content='runtime',
                     data_nature='IMPORTED_DATA', source_type='APIFY_REAL'),
            Evidence(id='ev-review-R2', source='Apify', content='clip',
                     data_nature='IMPORTED_DATA', source_type='APIFY_REAL'),
        ],
        voc={'review_count':2, 'coverage_level':'LOW_COVERAGE', 'status':'COMPLETED',
             'source_counts':{'APIFY_REAL':2, 'SAMPLE':0}, 'pain_points':[],
             'canonical_pain_points':[{
                 'canonical_pain_point':'续航有限', 'aspect':'runtime', 'mentions':1,
                 'sample_size':2, 'mention_rate':0.5, 'products':['A'],
                 'raw_pain_points':['short runtime'], 'evidence_ids':['ev-review-R1'],
                 'confidence':'LOW',
             }]},
        opportunities=[{
            'title':'续航机会', 'canonical_pain_points':['续航有限'],
            'evidence_ids':['ev-review-R2'],
        }],
        report={'markdown':'所有未知参数均为 UNKNOWN / NEED_VERIFY。'},
    )

    result = validate_report(state)

    assert result.status == 'FAIL'
    assert any('Evidence 不属于所绑定的 canonical pain point' in item for item in result.errors)


def test_real_validator_rejects_bad_product_and_corpus_rate_denominators():
    state = AnalysisState(
        project={'mode':'REAL_MODE'},
        evidence=[
            Evidence(id=f'ev-review-R{i}', source='Apify', content='heat',
                     data_nature='IMPORTED_DATA', source_type='APIFY_REAL')
            for i in range(1, 5)
        ],
        voc={
            'review_count':4, 'coverage_level':'LOW_COVERAGE', 'status':'COMPLETED',
            'source_counts':{'APIFY_REAL':4, 'SAMPLE':0},
            'product_review_counts':{'Nitecore':4}, 'pain_points':[],
            'canonical_pain_points':[{
                'canonical_pain_point':'高亮发热', 'aspect':'heat', 'mentions':4,
                'product_sample_size':13, 'product_mention_rate':1.2,
                'corpus_sample_size':26, 'corpus_mention_rate':0.9,
                'sample_size':26, 'mention_rate':0.9, 'products':['Nitecore'],
                'product_distribution':{'Nitecore':{
                    'mentions':3, 'sample_size':13, 'mention_rate':0.8}},
                'raw_pain_points':['hot'],
                'evidence_ids':[f'ev-review-R{i}' for i in range(1, 5)],
                'confidence':'MEDIUM',
            }],
        },
        report={'markdown':'所有未知参数均为 UNKNOWN / NEED_VERIFY。'},
    )

    result = validate_report(state)

    assert result.status == 'FAIL'
    assert any('product_mention_rate' in item for item in result.errors)
    assert any('corpus_sample_size' in item or 'corpus_mention_rate' in item for item in result.errors)
    assert any('product_distribution' in item and 'mentions' in item for item in result.errors)


def test_real_validator_rejects_non_pain_conclusion_without_real_evidence():
    state=AnalysisState(
        project={'mode':'REAL_MODE'},
        evidence=[Evidence(id='ev-review-R1',source='Apify',content='real',
                           data_nature='IMPORTED_DATA',source_type='APIFY_REAL')],
        voc={'review_count':1,'coverage_level':'LOW_COVERAGE','status':'COMPLETED',
             'source_counts':{'APIFY_REAL':1},'pain_points':[],
             'positive_feedback':[{'topic':'亮度','mention_count':1,'sample_size':1,
                                   'mention_rate':1.0,'evidence_ids':['ev-review-MISSING']}]},
        report={'markdown':'PEN-X1 的未知参数为 UNKNOWN / NEED_VERIFY。'}
    )
    result=validate_report(state)
    assert result.status == 'FAIL'
    assert any('Evidence' in item for item in result.errors)

def test_evidence_bound_review_numeric_text_is_supported_but_uncited_spec_is_not():
    evidence=Evidence(id='ev-review-R1',source='Apify',content='not 24 hours',
                      data_nature='IMPORTED_DATA',source_type='APIFY_REAL')
    supported=AnalysisState(
        project={'mode':'DEMO_MODE'}, evidence=[evidence],
        report={'markdown':'- 竞品评论提到 not 24 hours；Evidence：ev-review-R1。'})
    assert validate_report(supported).errors == []
    unsupported=AnalysisState(
        project={'mode':'DEMO_MODE'}, evidence=[evidence],
        report={'markdown':'PEN-X1 具有 24 hours 续航。'})
    assert validate_report(unsupported).status == 'FAIL'
