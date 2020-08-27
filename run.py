import itertools
import math
import os

import pandas as pd
import sklearn.preprocessing as pre

import api
import queries

# Pandas options
pd.set_option('max_rows', 10)
pd.set_option('max_columns', 10)
pd.set_option('expand_frame_repr', True)
pd.set_option('large_repr', 'truncate')
pd.options.display.float_format = '{:.2f}'.format


def filter_state(data: pd.DataFrame, state: str) -> pd.DataFrame:
    return data[data['State'].str.lower() == state.lower()]


def filter_counties(data: pd.DataFrame, counties: list) -> pd.DataFrame:
    return data[data['County Name'].str.lower().isin(counties)]


def clean_fred_data(data: pd.DataFrame) -> pd.DataFrame:
    data['Non-Home Ownership (%)'] = 100 - data['Home Ownership (%)']

    data.drop([
        'Home Ownership (%)',
        'county_id',
        'Burdened Households Date',
        'Home Ownership Date',
        'Income Inequality Date',
        'Population Below Poverty Line Date',
        'Single Parent Households Date',
        'SNAP Benefits Recipients Date',
        'Unemployment Rate Date',
        'Resident Population Date'
    ], axis=1, inplace=True)
    data = data.loc[:, ~data.columns.str.contains('^Unnamed')]

    return data


def percent_to_population(feature: str, name: str, df: pd.DataFrame) -> pd.DataFrame:
    df[name] = (df[feature] / 100) * df['Resident Population (Thousands of Persons)'] * 1000
    return df


def cross_features(df: pd.DataFrame) -> pd.DataFrame:
    cols = ['Pop Below Poverty Level', 'Pop Unemployed', 'Income Inequality (Ratio)', 'Non-Home Ownership Pop',
            'Num Burdened Households', 'Num Single Parent Households']
    all_combinations = []
    for r in range(2, len(cols)):
        combinations_list = list(itertools.combinations(cols, r))
        all_combinations += combinations_list
    all_combinations.pop(0)
    new_cols = []
    for combo in all_combinations:
        new_cols.append(cross(combo, df))

    crossed_df = pd.DataFrame(new_cols)
    crossed_df = crossed_df.T
    crossed_df['Mean'] = crossed_df.mean(axis=1)

    return crossed_df


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = percent_to_population('Population Below Poverty Line (%)', 'Pop Below Poverty Level', df)
    df = percent_to_population('Unemployment Rate (%)', 'Pop Unemployed', df)
    df = percent_to_population('Burdened Households (%)', 'Num Burdened Households', df)
    df = percent_to_population('Single Parent Households (%)', 'Num Single Parent Households', df)
    df = percent_to_population('Non-Home Ownership (%)', 'Non-Home Ownership Pop', df)

    if 'Policy Value' in list(df.columns) or 'Countdown' in list(df.columns):
        df = df.drop(['Policy Value', 'Countdown'], axis=1)

    df = df.drop(['Population Below Poverty Line (%)',
                  'Unemployment Rate (%)',
                  'Burdened Households (%)',
                  'Single Parent Households (%)',
                  'Non-Home Ownership (%)',
                  'Resident Population (Thousands of Persons)',
                  ], axis=1)

    scaler = pre.MaxAbsScaler()
    df_scaled = pd.DataFrame(scaler.fit_transform(df), index=df.index, columns=df.columns)

    return df_scaled


def normalize_column(df: pd.DataFrame, col: str) -> pd.DataFrame:
    scaler = pre.MaxAbsScaler()
    df[col] = scaler.fit_transform(df[col].values.reshape(-1, 1))

    return df


def normalize_percent(percent: float) -> float:
    return percent / 100


def cross(columns: tuple, df: pd.DataFrame) -> pd.Series:
    columns = list(columns)
    new_col = '_X_'.join(columns)
    new_series = pd.Series(df[columns].product(axis=1), name=new_col).abs()
    return new_series


def priority_indicator(socioeconomic_index: float, policy_index: float, time_left: int = 1) -> float:
    if time_left < 1:
        # Handle 0 values
        time_left = 1

    return float(socioeconomic_index) * (1 - float(policy_index)) / math.sqrt(time_left)


def rank_counties(df: pd.DataFrame, label: str) -> pd.DataFrame:
    analysis_df = normalize(df)
    crossed = cross_features(analysis_df)
    analysis_df['Crossed'] = crossed['Mean']
    analysis_df = normalize_column(analysis_df, 'Crossed')
    analysis_df['Policy Value'] = df['Policy Value']
    analysis_df['Countdown'] = df['Countdown']

    analysis_df['Relative Risk'] = analysis_df.sum(axis=1)
    max_sum = analysis_df['Relative Risk'].max()
    analysis_df['Relative Risk'] = (analysis_df['Relative Risk'] / max_sum)

    if 'Relative Risk' in list(analysis_df.columns):
        analysis_df['Rank'] = analysis_df.apply(
            lambda x: priority_indicator(x['Relative Risk'], x['Policy Value'], x['Countdown']), axis=1
        )
    else:
        print('Selected counties are not in the policy data! Fill out `Policy Workbook.xlsx` for the desired counties')

    analysis_df.to_excel('Output/' + label + '_overall_vulnerability.xlsx')

    return analysis_df


def load_all_data() -> pd.DataFrame:
    if os.path.exists("Output/all_tables.xlsx"):
        try:
            print('Using local `all_tables.xlsx`')
            df = pd.read_excel('Output/all_tables.xlsx')
        except:
            print('Something went wrong with the Excel file. Falling back to database query.')
            df = queries.latest_data_all_tables()
    else:
        df = queries.latest_data_all_tables()

    return df


def get_single_county(county: str, state: str) -> pd.DataFrame:
    df = load_all_data()

    df = filter_state(df, state)
    df = filter_counties(df, [county])
    df = get_existing_policies(df)
    print(df)

    df = clean_fred_data(df)
    print(df)

    df.set_index(['County Name'], drop=True, inplace=True)
    return df


def get_existing_policies(df):
    policy_df = queries.policy_query()
    temp_df = df.merge(policy_df, on='county_id')
    if not temp_df.empty:
        res = input('Policy data found in database. Use this data? [Y/n]').strip()
        if res.lower() == 'y' or res.lower() == 'yes' or res == '':
            return temp_df

    return df


def get_multiple_counties(counties: list, state: str) -> pd.DataFrame:
    df = load_all_data()

    df = filter_state(df, state)
    df = filter_counties(df, counties)
    df = get_existing_policies(df)
    df = clean_fred_data(df)

    df.set_index(['State', 'County Name'], drop=True, inplace=True)

    return df


def get_state_data(state: str) -> pd.DataFrame:
    df = load_all_data()
    df = clean_fred_data(df)

    df = filter_state(df, state)
    df.set_index(['State', 'County Name'], drop=True, inplace=True)

    return df


def output_table(df: pd.DataFrame, path: str):
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    df.to_excel(path)


def display_results(df):
    df.sort_values('Rank', ascending=False, inplace=True)
    print(df['Rank'])
    print('Ranked by overall priority, higher values mean higher priority.')


if __name__ == '__main__':
    if not os.path.exists('Output'):
        os.makedirs('Output')

    task = input('Analyze a single county (1), multiple counties (2), or all the counties in a state (3)? [default: 1]') \
        .strip()

    if task == '1' or task == '':
        res = input('Enter the county and state (ie: Jefferson County, Colorado):')
        res = res.strip().split(',')
        county = res[0].strip().lower()
        state = res[1].strip().lower()
        df = get_single_county(county, state)
        output_table(df, 'Output/' + county + '.xlsx')
        print('Done!')
    elif task == '2':
        state = input("Which state are you looking for (ie: California)?").strip()
        counties = input('Please specify one or more counties, separated by commas.').strip().split(',')
        counties = [_.strip().lower() for _ in counties]
        counties = [_ + ' county' for _ in counties if ' county' not in _]
        df = get_multiple_counties(counties, state)
        output_table(df, 'Output/' + state + '_selected_counties.xlsx')
        analysis_df = rank_counties(df, state + '_selected_counties')
        display_results(analysis_df)
        print('Done!')
    elif task == '3':
        state = input("Which state are you looking for (ie: California)?").strip()
        df = get_state_data(state)
        output_table(df, 'Output/' + state + '.xlsx')
        analysis_df = rank_counties(df, state)
        display_results(analysis_df)
        print('Done!')
    else:
        raise Exception('INVALID INPUT! Enter a valid task number.')
