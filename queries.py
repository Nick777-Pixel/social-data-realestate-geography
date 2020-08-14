import os
import sys
import psycopg2
import pandas as pd

conn = psycopg2.connect(
    dbname=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    port=os.getenv('DB_PORT'),
    host=os.getenv('DB_HOST')
)

all_tables = [
    'burdened_households', 
    'homeownership_rate', 
    'income_inequality', 
    'population_below_poverty', 
    'single_parent_households', 
    'snap_benefits_recipients', 
    'unemployment_rate'
]

table_headers = {
    'burdened_households': 'Burdened Households', 
    'homeownership_rate': 'Home Ownership', 
    'income_inequality': 'Income Inequality', 
    'population_below_poverty': 'Population Below Poverty Line', 
    'single_parent_households': 'Single Parent Households', 
    'snap_benefits_recipients': 'SNAP Benefits Recipients', 
    'unemployment_rate': 'Unemployment Rate'
}

table_units = {
    'burdened_households': '%', 
    'homeownership_rate': '%', 
    'income_inequality': 'Ratio', 
    'population_below_poverty': '%', 
    'single_parent_households': '%', 
    'snap_benefits_recipients': 'Persons', 
    'unemployment_rate': '%'
}

def counties_query(connection):
    cur = connection.cursor()
    cur.execute(
        'SELECT id as county_id, state as "State", name as "County Name" '
        'FROM counties'
    )
    colnames = [desc[0] for desc in cur.description]
    results = cur.fetchall()
    return pd.DataFrame(results, columns=colnames)


def latest_data_single_table(connection, table_name, require_counties=True):
    cur = connection.cursor()
    cur.execute(
        'SELECT DISTINCT ON (county_id) '
        'county_id, date AS "{} Date", value AS "{} ({})" '
        'FROM {} '
        'ORDER BY county_id , "date" DESC'.format(table_headers[table_name], table_headers[table_name], table_units[table_name], table_name))
    results = cur.fetchall()
    colnames = [desc[0] for desc in cur.description]
    df = pd.DataFrame(results, columns=colnames)
    if require_counties:
        counties_df = counties_query(connection)
        df = counties_df.merge(df)
    return df


def latest_data_all_tables(connection):
    cur = connection.cursor()
    counties_df = counties_query(connection)
    for table_name in all_tables:
        table_output = latest_data_single_table(connection, table_name, require_counties=False)
        counties_df = counties_df.merge(table_output)
    return counties_df


def output_data(df: pd.DataFrame, table_name='all_tables', ext='xlsx'):
    if not os.path.isdir('Output'):
        os.mkdir('Output')
    if ext == 'pk':
        path ='Output/{}.pk'.format(table_name) 
        df.to_pickle(path)
    elif ext == 'xlsx':
        path = 'Output/{}.xlsx'.format(table_name)
        df.to_excel(path)
    else:
        print('Only .pk and .xlsx outputs are currently supported.')
        sys.exit()
    return path

if __name__ == '__main__':
    
    args = {k: v for k, v in [i.split('=') for i in sys.argv[1:] if '=' in i]}

    table_name = args.get('--table', None)
    output_format = args.get('--output', None)
    
    if table_name:
        df = latest_data_single_table(conn, args['--table'])
    else:
        df = latest_data_all_tables(conn)

    if output_format:
        if table_name: 
            path = output_data(df, table_name=table_name, ext=output_format)
        else:
            path = output_data(df, ext=output_format)
    else:
        if table_name: 
            path =output_data(df, table_name=table_name)
        else:
            path =output_data(df)
    
    print('Successful query returned. Output at {}.'.format(path))
