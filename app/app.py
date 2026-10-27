"""HN Hiring Observatory: live Databricks analytics, local review or managed App."""
from datetime import date
from pathlib import Path
import json
import math
import logging
import time
import uuid
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
import plotly.express as px
import streamlit as st

from backend import Warehouse
from queries import query_for

st.set_page_config(page_title='HN Hiring Observatory', page_icon='◈', layout='wide', initial_sidebar_state='expanded')
st.markdown('<style>' + Path(__file__).with_name('style.css').read_text() + '</style>', unsafe_allow_html=True)
COLORS = ['#247B83', '#D65A31', '#5264A0', '#A37733', '#56715A', '#976681', '#6B8090', '#A65C55']
LOCAL = os.environ.get('HNJOB_LOCAL') == 'true'
QUERY_LOG = logging.getLogger('hnjob.queries')
QUERY_LOG.setLevel(logging.INFO)


@st.cache_resource
def warehouse():
    return Warehouse()


@st.cache_data(ttl=300, show_spinner=False)
def run_query(statement, params, generation=0):
    started = time.monotonic()
    try:
        result = warehouse().query(statement, params)
    except Exception as exc:
        QUERY_LOG.error('query_failed duration_seconds=%.3f error_type=%s', time.monotonic() - started, type(exc).__name__)
        raise
    QUERY_LOG.info('query_complete statement_id=%s duration_seconds=%.3f', result.statement_id, time.monotonic() - started)
    # Keep the cache independent of backend class identity across Streamlit reloads.
    # Cache data only, not the result wrapper or any transport/runtime state.
    return {'frame': result.frame, 'statement_id': str(result.statement_id),
            'truncated': bool(result.truncated)}


def load(name, filters=None, **options):
    statement, params = query_for(name, warehouse().namespace, filters, **options)
    try:
        with st.spinner('Reading the hiring dataset…'):
            result = run_query(statement, params, st.session_state.get('generation', 0))
    except Exception as exc:
        st.error('The data service could not complete this query.')
        reference = uuid.uuid4().hex[:12]
        logging.getLogger('hnjob.queries').error('query_failed query=%s reference=%s error_type=%s', name, reference, type(exc).__name__)
        st.caption('Please retry. If this continues, share reference ' + reference + ' with the operator.')
        if st.button('Retry data connection', key='retry_' + name):
            st.cache_data.clear(); st.rerun()
        st.stop()
    if result['truncated']:
        st.warning('This result reached its display limit. Narrow the filters before interpreting or exporting it.')
    return result['frame']


def sql_details(name, filters=None, **options):
    statement, params = query_for(name, warehouse().namespace, filters, **options)
    with st.expander('View SQL and parameters'):
        st.code(statement, language='sql')
        if params:
            st.json(params, expanded=False)


def chart(figure, key=None, height=330, percent=False):
    figure.update_layout(template='plotly_white', height=height, margin=dict(l=10, r=10, t=24, b=12),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='sans-serif', color='#384D5A'),
        legend=dict(orientation='h', y=1.15, x=0), colorway=COLORS)
    figure.update_xaxes(showgrid=False, title=None)
    figure.update_yaxes(gridcolor='#EAEFF2', title=None, rangemode='tozero')
    if percent:
        figure.update_yaxes(ticksuffix='%')
    st.plotly_chart(figure, width='stretch', key=key, config={'displaylogo': False})


def export(frame, filename, key):
    st.download_button('Download CSV', frame.to_csv(index=False).encode(), filename, 'text/csv', key=key)


def safe_list(value):
    return value if isinstance(value, list) else []


def monthly_grid(frame, start, end):
    grid = pd.DataFrame({'month': pd.period_range(start, end, freq='M').astype(str)})
    merged = grid.merge(frame, on='month', how='left')
    complete = coverage.set_index('month')['incomplete_posts'].to_dict()
    for column in ['advertisements', 'remote_ads', 'salary_ads']:
        if column in merged:
            known = merged.month.map(complete).eq(0)
            merged.loc[known, column] = merged.loc[known, column].fillna(0)
    return merged


def header(eyebrow, title, intro):
    st.markdown(f'<div class="eyebrow">{eyebrow}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="intro">{intro}</div>', unsafe_allow_html=True)


try:
    metadata = load('metadata').iloc[0]
    options = load('options')
    coverage = load('coverage')
except (KeyError, ValueError, OSError, RuntimeError) as exc:
    st.title('HN Hiring Observatory')
    st.info('Connect to the Databricks dataset to begin. Start locally with an explicitly selected profile.')
    st.code('.venv/bin/python run_local.py --profile tom')
    st.caption(str(exc)[:700])
    st.stop()

months = coverage.month.tolist()
complete_months = [m for m in months if m < date.today().strftime('%Y-%m')]
default_end = complete_months[-1] if complete_months else months[-1]
default_start = max(months[0], str(pd.Period(default_end, freq='M') - 11))

with st.sidebar:
    st.markdown('<div class="brand">HN<span> / </span>Observatory</div><div class="brand-sub">THE HIRING SIGNAL</div>', unsafe_allow_html=True)
    page = st.radio('Workspace', ['Overview', 'Your Next Skill', 'Skills', 'Compensation', 'Explore ads', 'Ask the data', 'Data coverage'], label_visibility='collapsed')
    st.divider()
    st.caption('FILTER THE MARKET')
    start = st.selectbox('From month', months, index=months.index(default_start), disabled=page == 'Your Next Skill')
    ends = [m for m in months if m >= start]
    end = st.selectbox('Through month', ends, index=ends.index(default_end) if default_end in ends else len(ends)-1, disabled=page == 'Your Next Skill')
    countries = sorted(options.loc[options.kind == 'country', 'value'].dropna().tolist())
    country = st.selectbox('Country', ['All countries'] + countries)
    policy = st.selectbox('Work policy', ['All policies', 'remote', 'hybrid', 'onsite', 'unspecified'])
    seniority = st.selectbox('Seniority', ['All levels', 'intern', 'junior', 'mid', 'senior', 'staff', 'principal', 'leadership', 'unspecified'])
    st.caption('Filters match whole advertisements. Attributes can describe different roles within the same post.')
    filters = dict(start=start, end=end, country='' if country == 'All countries' else country,
                   policy='' if policy == 'All policies' else policy,
                   seniority='' if seniority == 'All levels' else seniority)
    st.divider()
    st.caption(f"{int(metadata.hiring_ads):,} hiring ads · {int(metadata.months)} months")
    st.caption('Source: official HN monthly threads')
    st.caption(f"Retrieved {str(metadata.fetched_at)[:16]} UTC")
    st.caption(f"Extracted {str(metadata.extracted_at)[:16]} UTC · cached 5 min")
    if st.button('Refresh results', width='stretch'):
        st.cache_data.clear()
        st.session_state['generation'] = st.session_state.get('generation', 0) + 1
        st.rerun()
    if LOCAL:
        st.caption(f"LOCAL REVIEW · profile {os.environ.get('DATABRICKS_CONFIG_PROFILE', 'unset')}")

selected_coverage = coverage[coverage.month.between(start, end)]
if page != 'Your Next Skill' and (selected_coverage.incomplete_posts.gt(0).any() or len(selected_coverage) != len(pd.period_range(start, end, freq='M'))):
    st.warning('The selected range has incomplete processing or missing months. Charts describe the available subset.')
if page != 'Your Next Skill' and selected_coverage.partial_month.fillna(False).any():
    st.info('This selection includes a partial month. It is excluded from automatic skill-growth comparisons.')

period_label = f'{start} → {end}'
skill_options = sorted(options.loc[options.kind == 'skill', 'value'].dropna().tolist())


def overview():
    header('MARKET PULSE', 'A clearer view of tech hiring.',
           'Follow what companies are looking for, through the lens of Hacker News hiring posts. Explore the signal, then trace it back to the source.')
    monthly = monthly_grid(load('monthly', filters), start, end)
    total = int(monthly.advertisements.sum())
    length = len(pd.period_range(start, end, freq='M'))
    previous_end = str(pd.Period(start, freq='M') - 1)
    previous_start = str(pd.Period(start, freq='M') - length)
    previous = load('monthly', {**filters, 'start': previous_start, 'end': previous_end}) if previous_start >= months[0] else pd.DataFrame()
    previous_total = previous.advertisements.sum() if not previous.empty else 0
    delta = f'{100 * (total / previous_total - 1):+.1f}% vs prior {length} months' if previous_total else None
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Hiring advertisements', f'{total:,}', delta, delta_color='off')
    c2.metric('Ads allowing remote work', f'{100 * monthly.remote_ads.sum() / total:.1f}%' if total else '—')
    c3.metric('Ads with numeric compensation', f'{100 * monthly.salary_ads.sum() / total:.1f}%' if total else '—')
    c4.metric('Months in view', str(length))
    st.caption(f'{period_label} · distinct hiring ads · remote can coexist with other policies · numeric compensation includes all stated types')
    if not total:
        st.info('No hiring advertisements match these filters. Widen the dates or clear a filter.'); return
    with st.container(border=True):
        st.subheader('Hiring activity over time')
        st.caption('Each advertisement counts once. Reposts in different months remain distinct.')
        chart(px.area(monthly, x='month', y='advertisements', color_discrete_sequence=[COLORS[0]]), 'market')
        sql_details('monthly', filters)
    a, b = st.columns([1.15, 1])
    with a, st.container(border=True):
        st.subheader('The most-mentioned skills')
        top = load('skills', filters).head(12).sort_values('advertisements')
        chart(px.bar(top, x='advertisements', y='skill', orientation='h', color_discrete_sequence=[COLORS[0]]), 'topskills', height=400)
    with b, st.container(border=True):
        st.subheader('Where work happens')
        work = load('policies', filters)
        work['share_pct'] = 100 * work.advertisements / total
        chart(px.bar(work, x='label', y='share_pct', color_discrete_sequence=[COLORS[0]]), 'policies', percent=True, height=300)
        st.caption('A post can advertise multiple policies. Shares need not add to 100%; unspecified stays visible.')
    a, b = st.columns(2)
    with a, st.container(border=True):
        st.subheader('Seniority mentioned')
        levels = load('seniority', filters).sort_values('advertisements')
        chart(px.bar(levels, x='advertisements', y='label', orientation='h', color_discrete_sequence=[COLORS[2]]), 'levels')
    with b, st.container(border=True):
        st.subheader('Advertised work locations')
        places = load('countries', filters).head(10).sort_values('advertisements')
        if places.empty: st.info('No specific countries are listed for this selection.')
        else: chart(px.bar(places, x='advertisements', y='label', orientation='h', color_discrete_sequence=[COLORS[2]]), 'places')
        st.caption('Location context, not proof of remote eligibility. Worldwide and region-only posts may have no country.')


def skills_page():
    header('SKILL INTELLIGENCE', 'Follow the changing stack.', 'Compare prevalence over time and see which technologies are gaining share of hiring advertisements.')
    st.caption('The skill selector contains the 400 most-mentioned normalized skills in the full corpus.')
    selected = st.multiselect('Skills to track', skill_options,
        default=[s for s in ['python', 'typescript', 'rust'] if s in skill_options], max_selections=8)
    monthly = monthly_grid(load('monthly', filters), start, end)
    if selected:
        trend = load('skill_trend', filters, skills=selected)
        grid = pd.MultiIndex.from_product([monthly.month, selected], names=['month', 'skill']).to_frame(index=False)
        series = grid.merge(trend[['month', 'skill', 'advertisements']], how='left').merge(
            monthly[['month', 'advertisements']].rename(columns={'advertisements': 'all_ads'}), on='month')
        series['share_pct'] = 100 * series.advertisements.fillna(0) / series.all_ads.replace(0, float('nan'))
        with st.container(border=True):
            st.subheader('Share of hiring ads mentioning each skill')
            chart(px.line(series, x='month', y='share_pct', color='skill', color_discrete_sequence=COLORS), 'skilltrend', height=380, percent=True)
            sql_details('skill_trend', filters, skills=selected)
            export(series, 'skill-prevalence.csv', 'trendcsv')
    st.subheader('Who is gaining ground?')
    c1, c2 = st.columns(2)
    window = c1.selectbox('Months per comparison period', [3, 6, 12])
    minimum = int(c2.number_input('Minimum mentions in each period', min_value=1, max_value=500, value=20))
    recent_end = min(end, default_end)
    recent_start = str(pd.Period(recent_end, freq='M') - window + 1)
    prior_start = str(pd.Period(recent_start, freq='M') - window)
    prior_end = str(pd.Period(recent_start, freq='M') - 1)
    st.caption(f'Previous: {prior_start}–{prior_end} · Recent: {recent_start}–{recent_end}. Country, policy and seniority filters apply to both periods.')
    if prior_start < months[0]:
        st.info('Choose a later end month or a shorter comparison period.'); return
    if coverage[coverage.month.between(prior_start, recent_end)].incomplete_posts.gt(0).any():
        st.warning('Some comparison months are incompletely processed; growth describes the processed subset.')
    growth_options = dict(prior_start=prior_start, recent_start=recent_start, recent_end=recent_end, minimum=minimum)
    growth = load('growth', filters, **growth_options)
    if growth.empty:
        st.info('No skills meet the sample threshold in both periods. Lower the threshold or widen the selection.'); return
    st.caption(f"Denominators: {int(growth.previous_total.iloc[0]):,} previous ads → {int(growth.recent_total.iloc[0]):,} recent ads. Ranked by percentage-point change, not raw-count growth.")
    with st.container(border=True):
        top = growth[growth.growth_pp > 0].head(15).sort_values('growth_pp')
        if top.empty: st.info('No qualifying skills gained share during this comparison.')
        else:
            figure = px.bar(top, x='growth_pp', y='skill', orientation='h', color_discrete_sequence=[COLORS[0]])
            figure.update_xaxes(ticksuffix=' pp')
            chart(figure, 'growth', height=430)
    st.dataframe(growth, hide_index=True, width='stretch', column_config={
        'previous_share_pct': st.column_config.NumberColumn('Previous share %', format='%.2f'),
        'recent_share_pct': st.column_config.NumberColumn('Recent share %', format='%.2f'),
        'growth_pp': st.column_config.NumberColumn('Change (pp)', format='%+.2f'),
        'relative_growth_pct': st.column_config.NumberColumn('Relative growth %', format='%+.1f')})
    st.caption('Showing up to 30 qualifying skills. Small or zero-baseline skills below the threshold are excluded. Growth in share can occur while raw mentions fall.')
    sql_details('growth', filters, **growth_options)
    export(growth, 'skill-growth.csv', 'growthcsv')


def compensation():
    header('COMPENSATION', 'What the numbers actually say.', 'Compare explicitly advertised compensation within a single currency, pay period and compensation type. Unknown values remain unknown.')
    st.caption(f'{period_label} · {int(metadata.salary_flags)} invalid-bound posts are excluded. A range midpoint is not actual employee pay.')
    st.caption('Filters select whole advertisements; a salary range may belong to a different opening within a matching post.')
    combinations = load('salary_options', filters)
    valid = combinations[combinations.currency.notna() & combinations.period.notna() & combinations.type.notna()]
    valid = valid[~valid.currency.isin(['unspecified', 'unknown', '']) &
                  ~valid.period.isin(['unspecified', 'unknown', '']) & valid.type.isin(['base', 'total'])]
    if valid.empty:
        st.info('No ranges with a known currency, period and base/total type match this selection. Widen the dates or inspect source quotes in Explore ads.'); return
    c1, c2, c3 = st.columns(3)
    currencies = sorted(valid.currency.unique().tolist())
    currency = c1.selectbox('Currency', currencies, index=currencies.index('USD') if 'USD' in currencies else 0)
    periods = sorted(valid[valid.currency == currency].period.unique().tolist())
    period = c2.selectbox('Pay period', periods, index=periods.index('annual') if 'annual' in periods else 0)
    types = sorted(valid[(valid.currency == currency) & (valid.period == period)].type.unique().tolist())
    kind = c3.selectbox('Compensation type', types, index=types.index('base') if 'base' in types else 0)
    arguments = dict(currency=currency, period=period, compensation_type=kind)
    salaries = load('salaries', filters, **arguments)
    if salaries.empty: st.info('No ranges match the chosen combination.'); return
    a, b, c = st.columns(3)
    a.metric('Comparable ranges shown', f'{len(salaries):,}')
    b.metric(f'Median range midpoint · {currency}', f'{salaries.midpoint.median():,.0f}')
    c.metric('Distinct advertisements shown', f'{salaries.comment_id.nunique():,}')
    st.caption(f'{currency} · {period} · {kind}. One post can contain several ranges. Only positive, ordered two-sided ranges with explicit type and period are included; nothing is converted or annualized.')
    st.caption('Displays up to the 2,000 most recent matching ranges; narrow the dates for a smaller sample.')
    with st.container(border=True):
        st.subheader('Distribution of advertised range midpoints')
        chart(px.box(salaries.sort_values('month'), x='month', y='midpoint', points=False,
                     color_discrete_sequence=[COLORS[0]]), 'salarybox', height=400)
    with st.expander('Source ranges and evidence', expanded=True):
        st.dataframe(salaries[['company', 'month', 'title', 'minimum', 'maximum', 'original_text', 'source_url']],
            hide_index=True, width='stretch', column_config={'source_url': st.column_config.LinkColumn('HN source')})
    sql_details('salaries', filters, **arguments)
    export(salaries, 'compensation-ranges.csv', 'salarycsv')
    st.caption(f"Across this selection, {int(combinations['ranges'].sum()):,} ordered ranges have identifiable bounds; ambiguous currency/period/type are not silently reclassified.")


def explorer():
    header('SOURCE EXPLORER', 'Go straight to the source.', 'Find advertisements, inspect what the AI extracted, and compare it with the original words.')
    with st.form('searchform'):
        term = st.text_input('Search the post text', placeholder='Company, job title, technology or location…')
        c1, c2 = st.columns([3, 1])
        skill = c1.selectbox('Normalized skill', ['Any skill'] + skill_options)
        page_number = int(c2.number_input('Page', min_value=1, value=1))
        st.form_submit_button('Search advertisements', type='primary')
    arguments = dict(term=term.strip(), skill='' if skill == 'Any skill' else skill, page=page_number)
    count = int(load('explorer_count', filters, **arguments).advertisements.iloc[0])
    pages = max(1, math.ceil(count / 20))
    st.caption(f'{count:,} matching advertisements · page {page_number} of {pages} · 20 per page · {period_label}')
    if page_number > pages:
        st.info(f'Choose page {pages} or earlier.'); return
    ads = load('explorer', filters, **arguments)
    if ads.empty: st.info('No matching ads. Try fewer filters or a broader search.'); return
    st.caption('All attributes describe the whole post. A country, skill or policy may apply to only one of its advertised roles.')
    for ad in ads.to_dict('records'):
        with st.expander(f"{ad['company'] or 'Company unspecified'}  ·  {ad['month']}  ·  HN {ad['comment_id']}"):
            a, b = st.columns([4, 1])
            a.write('**Work policy:** ' + ', '.join(safe_list(ad['remote_policy'])))
            b.link_button('Original HN post ↗', ad['source_url'])
            st.caption('Countries: ' + (', '.join(safe_list(ad['countries'])) or ', '.join(safe_list(ad['country_scope']))) + ' · Seniority: ' + ', '.join(safe_list(ad['seniority'])))
            st.write('**Skills:** ' + (', '.join(safe_list(ad['skills'])) or 'None explicitly named'))
            if not ad['evidence_quotes_verified'] or not ad['salary_bounds_valid'] or ad['country_review_status'] == 'needs_review':
                st.warning('This post has a quality review flag. Verify extracted facts against the source.')
            if safe_list(ad['salary']): st.dataframe(pd.DataFrame(ad['salary']), hide_index=True, width='stretch')
            st.markdown('**Original post**')
            st.text(ad['source_text'])
            st.markdown('**Extracted evidence**')
            st.json(ad['evidence'], expanded=False)
    sql_details('explorer', filters, **arguments)
    export(ads, 'advertisements-page.csv', 'adscsv')


def render_answer(item, index):
    with st.chat_message(item['role']):
        st.write(item['content'])
        if item.get('sql'):
            with st.expander('Generated SQL', expanded=False): st.code(item['sql'], language='sql')
        if 'rows' in item:
            frame = pd.DataFrame(item['rows'], columns=item['columns'])
            if frame.empty: st.info('The query completed and returned no matching rows.')
            else:
                st.dataframe(frame, width='stretch', hide_index=True, column_config={
                    col: st.column_config.LinkColumn(col) for col in frame.columns if col.endswith('source_url')})
                numeric = [c for c in frame.columns[1:] if pd.to_numeric(frame[c], errors='coerce').notna().all()]
                preferred = ['growth_pp', 'growth_percentage_points', 'share_pct', 'share_percent', 'advertisements']
                numeric.sort(key=lambda col: preferred.index(col) if col in preferred else len(preferred))
                if 1 < len(frame) <= 100 and numeric:
                    col = numeric[0]
                    st.caption(f'{col} by {frame.columns[0]}')
                    plotted = frame.copy(); plotted[col] = pd.to_numeric(plotted[col])
                    figure = px.line(plotted, x=frame.columns[0], y=col, markers=True) if 'month' in frame.columns[0].lower() else px.bar(plotted, x=frame.columns[0], y=col)
                    chart(figure, key=f'answer_{index}')
                export(frame, 'chat-result.csv', f'chatcsv_{index}')
            if item.get('truncated'): st.warning('Results were truncated. Ask a narrower question.')
        if item['role'] == 'assistant':
            st.caption('AI-generated SQL — verify the method and source data. This result measures HN posting activity, not actual hires.')


def chat_page():
    header('ASK THE OBSERVATORY', 'A question is a good starting point.', 'Ask about the hiring market in plain English. Every data answer includes the SQL that produced it and the returned results.')
    identity = f"Local profile: {os.environ.get('DATABRICKS_CONFIG_PROFILE', 'unset')}" if LOCAL else 'Execution identity: app service principal'
    st.caption(identity + ' · five curated HN tables/views · current filters are defaults; explicit dates in your question override them')
    with st.expander('How this assistant works'):
        st.write('A Databricks-hosted model proposes SQL using the dataset schema. The app checks the SQL for a single read-only query, allowed functions and project tables, then executes it on the warehouse. It cannot modify data. Results are capped at 200 rows. Unknown or unsupported questions should receive a clarification.')
        st.caption('Model: ' + os.environ.get('HNJOB_CHAT_MODEL', 'databricks-gpt-oss-120b'))
    history = st.session_state.setdefault('chat_history', [])
    if st.button('New conversation'):
        st.session_state.chat_history = []; st.rerun()
    suggestions = ['Which skills grew fastest in Q3 2026 versus Q2 2026?',
        'How has the share of Python ads changed since 2020?', 'Show five recent remote Rust ads with HN links.']
    suggestion = None
    if not history:
        st.caption('TRY A QUESTION')
        for i, question in enumerate(suggestions):
            if st.button(question, key=f'suggestion_{i}'): suggestion = question
    for index, item in enumerate(history): render_answer(item, index)
    question = st.chat_input('Ask a question about HN hiring…', max_chars=2000) or suggestion
    if not question: return
    history.append({'role': 'user', 'content': question})
    with st.chat_message('user'): st.write(question)
    answer = {'role': 'assistant', 'content': ''}
    with st.status('Understanding your question…', expanded=True) as status:
        try:
            plan = warehouse().plan_answer(question, {**filters, 'latest_complete_month': default_end},
                [{'role': h['role'], 'content': h['content']} for h in history[:-1]])
            if not plan.get('sql'):
                answer['content'] = plan.get('clarification') or plan['summary']
                status.update(label='A clarification is needed', state='complete', expanded=False)
            else:
                answer['sql'] = plan['sql']
                st.write('SQL checks passed. Reading the dataset…')
                result = warehouse().query(plan['sql'], max_rows=200)
                answer.update(content=plan['summary'], rows=result.frame.to_dict('records'),
                    columns=result.frame.columns.tolist(), truncated=result.truncated,
                    statement_id=result.statement_id)
                status.update(label='Query completed', state='complete', expanded=False)
        except Exception as exc:
            answer['content'] = 'The question could not be completed. ' + str(exc)[:650]
            status.update(label='Unable to complete this question', state='error', expanded=False)
    history.append(answer)
    st.rerun()


def health_page():
    header('DATA & METHODOLOGY', 'Know what is behind the chart.', 'A transparent view of source coverage, extraction quality and the limits of this dataset.')
    a, b, c, d = st.columns(4)
    a.metric('Source posts processed', f'{int(metadata.total_posts):,}')
    b.metric('Hiring ads classified', f'{int(metadata.hiring_ads):,}')
    c.metric('Incomplete outputs', f'{int(metadata.incomplete):,}')
    d.metric('Monthly threads', f'{int(coverage.threads.sum()):,}')
    st.subheader('Source and processing coverage')
    st.dataframe(coverage, hide_index=True, width='stretch')
    export(coverage, 'data-coverage.csv', 'coveragecsv')
    a, b, c = st.columns(3)
    a.metric('Evidence quotes to review', f'{int(metadata.evidence_flags):,}')
    b.metric('Country contexts to review', f'{int(metadata.country_flags):,}')
    c.metric('Invalid salary-bound posts', f'{int(metadata.salary_flags):,}')
    st.caption('Review flags can overlap. Successful processing means a valid response was saved, not that every extracted fact is correct.')
    with st.container(border=True):
        st.subheader('How to interpret the data')
        st.markdown('''
- **Source:** official monthly Hacker News “Who is hiring?” threads since January 2020. Direct comments only; nested discussions are excluded.
- **Grain:** one source comment is one advertisement. Reposts remain separate posting activity. A post can advertise multiple roles; attributes are a union across the post.
- **Coverage:** deleted/dead/unavailable historical text cannot be recovered. Partial months are labeled; missing months are not zero demand.
- **Skills:** explicitly named technologies, including product stacks and nice-to-haves. The alias map is useful but not an exhaustive taxonomy.
- **Compensation:** explicit numeric advertised ranges only. No currency conversion, annualization, or inference of USD from a dollar sign. Midpoints are not actual pay.
- **Country:** hiring-location context does not automatically establish remote eligibility. Worldwide and region-only are separate scopes.
- **AI quality:** GPT OSS 120B led a five-model development comparison on 20 posts (19/20 raw complete-post checks). This is not held-out or corpus-wide accuracy.
- **Refresh:** ingestion and extraction are triggered manually in Databricks. “Refresh results” reloads cached analytics; it does not fetch or reprocess posts.
''')
    sql_details('coverage')


from next_skill_ui import render as render_next_skill

{'Your Next Skill': lambda: render_next_skill(load, sql_details, coverage, metadata, skill_options, filters),
 'Overview': overview, 'Skills': skills_page, 'Compensation': compensation,
 'Explore ads': explorer, 'Ask the data': chat_page, 'Data coverage': health_page}[page]()
st.markdown('<div class="source-note">HN HIRING OBSERVATORY · Official monthly threads since 2020 · Extracted attributes are AI-derived · Counts describe advertisements, not vacancies or the entire tech labor market.</div>', unsafe_allow_html=True)
