"""Small, inspectable learning-direction workflow; no model calls."""
import pandas as pd
import streamlit as st
from next_skill import comparison_periods, is_stale


def render(load, sql_details, coverage, metadata, skill_options, filters):
    st.title('Your Next Skill')
    st.write('Find technologies mentioned alongside skills you already know, then explore the evidence.')
    periods = comparison_periods(coverage)
    st.caption(f"Recent: {periods['recent_start']}–{periods['recent_end']} · Previous: {periods['prior_start']}–{periods['prior_end']}")
    st.caption('Country, work policy and seniority filters apply. This screen always uses the latest completed three months; sidebar dates do not apply.')
    st.caption(f"Source retrieved {metadata.fetched_at} UTC · results cached for five minutes")
    if is_stale(metadata.fetched_at):
        st.warning('The source has not been retrieved within the last seven days. Refresh the dataset before relying on these suggestions.')
    if not periods['recent_complete']:
        st.warning('Recommendations are unavailable: the latest three completed months have missing or incomplete ingestion or extraction. Refresh and verify the dataset, then retry.')
        return
    # Keep selections when navigating to another screen; widget keys alone are cleaned up by Streamlit.
    selected = st.multiselect('Skills you already know', skill_options,
        default=st.session_state.get('next_skill_selection', []), max_selections=5)
    st.session_state['next_skill_selection'] = selected
    st.caption('Choose 1–5 skills from the 400 most-mentioned normalized skills.')
    context = {k: filters[k] for k in ['country', 'policy', 'seniority']}
    signature = (tuple(sorted(selected)), tuple(context.values()), periods['recent_end'])
    submitted = st.button('Find adjacent skills', type='primary')
    if submitted:
        if not selected:
            st.info('Choose at least one skill to begin.'); return
        st.session_state['next_skill_request'] = signature
    if st.session_state.get('next_skill_request') != signature:
        st.info('Choose your skills and select Find adjacent skills.'); return
    args = {k: periods[k] for k in ['prior_start', 'recent_start', 'recent_end']}
    args['skills'] = sorted(selected)
    results = load('next_skills', context, **args)
    total = int(results.recent_total.iloc[0])
    st.metric('Ads mentioning at least one of your skills', f'{total:,}')
    st.caption('One advertisement counts once, even when it mentions several selected skills. Reposts in different months count separately.')
    if total < 20:
        st.info('Not enough data: at least 20 relevant ads are needed. Try broader preferences or different skills.'); return
    results = results[results.skill.notna()].copy()
    if results.empty:
        st.info('No additional skill appears in at least five relevant ads. Try broader preferences or different skills.'); return
    if not periods['prior_complete']:
        results['previous_share_pct'] = float('nan')
    results['growth_pp'] = results.recent_share_pct - results.previous_share_pct
    results['alongside_skills'] = results.apply(lambda row: ', '.join(
        s for i, s in enumerate(sorted(selected)) if row[f'alongside_{i}'] == 1), axis=1)
    st.caption('Ranked by share of your relevant ads, then alphabetically for ties. Trends provide context; they do not change the ranking.')
    st.info('These are technologies to investigate, not proof of job eligibility. Skills may describe different roles, product stacks or nice-to-haves within the same post. Country mentions do not establish remote eligibility.')
    evidence = load('next_skill_evidence', context, **args, candidates=results.skill.tolist())
    for row in results.to_dict('records'):
        with st.container(border=True):
            st.subheader(row['skill'])
            st.write(f"{row['skill']} appears in **{int(row['recent_mentions'])} of {total} ads ({row['recent_share_pct']:.1f}%)** mentioning at least one of your selected skills.")
            st.write('Appears alongside: ' + row['alongside_skills'])
            if pd.isna(row['growth_pp']):
                st.caption('Not enough data for comparison: prior coverage must be complete and contain at least 20 relevant ads.')
            else:
                st.caption(f"Previous: {int(row['previous_mentions'])}/{int(row['previous_total'])} ads ({row['previous_share_pct']:.1f}%) · Change: {row['growth_pp']:+.2f} percentage points")
            for ad in evidence[evidence.skill == row['skill']].to_dict('records'):
                with st.expander(f"{ad['company'] or 'Company unspecified'} · {ad['month']} · HN {ad['comment_id']}"):
                    if ad['evidence_quotes_verified'] is not True or ad['country_review_status'] == 'needs_review':
                        st.caption('Extraction has a review flag. Verify the original wording.')
                    st.link_button('Read original HN post', ad['source_url'])
                    st.text(ad['source_text'])
    export = results.drop(columns=[c for c in results if c.startswith('alongside_') and c != 'alongside_skills'])
    for key in ['recent_start', 'recent_end', 'prior_start', 'prior_end', 'prior_complete']:
        export[key] = periods[key]
    for key, value in context.items(): export[key] = value
    export['selected_skills'] = ', '.join(sorted(selected))
    export['source_retrieved_at'] = str(metadata.fetched_at)
    export['minimum_cohort_ads'] = 20
    export['minimum_supporting_ads'] = 5
    st.download_button('Download recommendations CSV', export.to_csv(index=False).encode(),
                       'your-next-skill.csv', 'text/csv')
    sql_details('next_skills', context, **args)
