from app.schemas.models import Evidence, Fact
from app.schemas.state import AnalysisState
from app.skills.opportunity_analysis import run_opportunity_analysis

def test_opportunity_requires_four_evidence_classes_and_uses_fact_ids():
    state = AnalysisState(
      facts=[Fact(id='battery_configurations', category='project', name='battery configurations', value=['14500','AA'], data_nature='FACT')],
      evidence=[Evidence(id='ev-review-r1', source='csv', content='battery concern', data_nature='SAMPLE'), Evidence(id='ev-competitor-a', source='fixture', content='single battery family', data_nature='PUBLIC_FIXTURE'), Evidence(id='ev-market-1', source='fixture', content='market pattern', data_nature='PUBLIC_FIXTURE')],
      voc={'pain_points':[{'aspect':'battery','pain_point':'电池适配与可获得性','evidence_review_ids':['ev-review-r1']}]},
      competitors=[{'limitations':['single battery family']}], market={'research':{'sources':[{'status':'PUBLIC_FIXTURE'}]}}
    )
    result = run_opportunity_analysis(state)
    assert result[0]['product_fact_ids'] == ['battery_configurations']
    assert result[0]['voc_evidence'] == ['ev-review-r1']
    assert result[0]['competitor_evidence'] == ['ev-competitor-a']
    assert result[0]['status'] == 'INFERRED'
