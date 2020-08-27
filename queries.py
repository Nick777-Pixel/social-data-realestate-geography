import os
import sys
import psycopg2
import pandas as pd

import credentials

conn = psycopg2.connect(
    dbname=credentials.DB_NAME,
    user=credentials.DB_USER,
    password=credentials.DB_PASSWORD,
    port=credentials.DB_PORT,
    host=credentials.DB_HOST
)

fred_tables = [
    'burdened_households',
    'homeownership_rate',
    'income_inequality',
    'population_below_poverty',
    'single_parent_households',
    'snap_benefits_recipients',
    'unemployment_rate',
    'resident_population',
]

static_tables = [
    'chmura_economic_vulnerability_index',
    'median_rents',
    'fair_market_rents'
]

static_columns = {
    'chmura_economic_vulnerability_index': ['VulnerabilityIndex', 'Rank'],
    'fair_market_rents': ['fmr_0', 'fmr_1', 'fmr_2', 'fmr_3', 'fmr_4', ],
    'median_rents': ['rent50_0', 'rent50_1', 'rent50_2', 'rent50_3', 'rent50_4', ]
}

table_headers = {
    'burdened_households': 'Burdened Households',
    'homeownership_rate': 'Home Ownership',
    'income_inequality': 'Income Inequality',
    'population_below_poverty': 'Population Below Poverty Line',
    'single_parent_households': 'Single Parent Households',
    'snap_benefits_recipients': 'SNAP Benefits Recipients',
    'unemployment_rate': 'Unemployment Rate',
    'resident_population': 'Resident Population',
}

table_units = {
    'burdened_households': '%',
    'homeownership_rate': '%',
    'income_inequality': 'Ratio',
    'population_below_poverty': '%',
    'single_parent_households': '%',
    'snap_benefits_recipients': 'Persons',
    'unemployment_rate': '%',
    'resident_population': 'Thousands of Persons',
}


def counties_query() -> pd.DataFrame:
    cur = conn.cursor()
    cur.execute(
        'SELECT id as county_id, state as "State", name as "County Name" '
        'FROM counties'
    )
    colnames = [desc[0] for desc in cur.description]
    results = cur.fetchall()
    return pd.DataFrame(results, columns=colnames)


def policy_query() -> pd.DataFrame:
    cur = conn.cursor()
    cur.execute(
        'SELECT county_id as county_id, policy_value as "Policy Value", countdown as "Countdown" '
        'FROM policy'
    )
    colnames = [desc[0] for desc in cur.description]
    results = cur.fetchall()
    return pd.DataFrame(results, columns=colnames)


def latest_data_single_table(table_name: str, require_counties: bool = True) -> pd.DataFrame:
    cur = conn.cursor()
    cur.execute(
        'SELECT DISTINCT ON (county_id) '
        'county_id, date AS "{} Date", value AS "{} ({})" '
        'FROM {} '
        'ORDER BY county_id , "date" DESC'.format(table_headers[table_name], table_headers[table_name],
                                                  table_units[table_name], table_name))
    results = cur.fetchall()
    colnames = [desc[0] for desc in cur.description]
    df = pd.DataFrame(results, columns=colnames)
    if require_counties:
        counties_df = counties_query()
        df = counties_df.merge(df)
    return df


def latest_data_all_tables() -> pd.DataFrame:
    counties_df = counties_query()
    for table_name in fred_tables:
        table_output = latest_data_single_table(table_name, require_counties=False)
        counties_df = counties_df.merge(table_output)
    chmura_df = static_data_single_table('chmura_economic_vulnerability_index', ['VulnerabilityIndex'])
    counties_df = counties_df.merge(chmura_df)

    return counties_df


def static_data_single_table(table_name: str, columns: list) -> pd.DataFrame:
    cur = conn.cursor()
    str_columns = ', '.join('"{}"'.format(c) for c in columns)
    query = 'SELECT county_id, {} FROM {} '.format(str_columns, table_name)
    cur.execute(query)
    results = cur.fetchall()
    colnames = [desc[0] for desc in cur.description]
    df = pd.DataFrame(results, columns=colnames)
    counties_df = counties_query()
    df = counties_df.merge(df)
    return df


def static_data_all_table() -> pd.DataFrame:
    counties_df = counties_query()
    for table_name in static_tables:
        table_output = static_data_single_table(table_name, static_columns[table_name])
        counties_df = counties_df.merge(table_output)
    return counties_df


def output_data(df: pd.DataFrame, table_name: str = 'fred_tables', ext: str = 'xlsx') -> str:
    if not os.path.isdir('Output'):
        os.mkdir('Output')
    if ext == 'pk':
        path = 'Output/{}.pk'.format(table_name)
        df.to_pickle(path)
    elif ext == 'xlsx':
        path = 'Output/{}.xlsx'.format(table_name)
        df.to_excel(path)
    else:
        print('Only .pk and .xlsx outputs are currently supported.')
        sys.exit()
    return path

def fmr_data():
    cur = conn.cursor()
    cur.execute(
        'SELECT state_full as "State", countyname as "County Name" '
        'FROM fair_market_rents'
    )
    colnames = [desc[0] for desc in cur.description]
    results = cur.fetchall()
    return pd.DataFrame(results, columns=colnames)


if __name__ == '__main__':
    args = {k: v for k, v in [i.split('=') for i in sys.argv[1:] if '=' in i]}
    table = args.get('--table', None)
    output_format = args.get('--output', None)

    if table:
        df = latest_data_single_table(table)
    else:
        df = latest_data_all_tables()

    if output_format:
        if table:
            path = output_data(df, table_name=table, ext=output_format)
        else:
            path = output_data(df, ext=output_format)
    else:
        if table:
            path = output_data(df, table_name=table)
        else:
            path = output_data(df)

    print('Successful query returned. Output at {}.'.format(path))
