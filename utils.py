import base64
import pandas as pd
from six import BytesIO
import geopandas as gpd

def to_excel(df: pd.DataFrame):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, sheet_name='Sheet1')
    writer.save()
    processed_data = output.getvalue()
    return processed_data


def get_table_download_link(df: pd.DataFrame, file_name: str, text: str):
    """Generates a link allowing the data in a given panda dataframe to be downloaded
    in:  dataframe
    out: href string
    """
    val = to_excel(df)
    b64 = base64.b64encode(val)  # val looks like b'...'
    return f'<a href="data:application/octet-stream;base64,{b64.decode()}" download="{file_name}.xlsx">{text}</a>'


def output_table(df: pd.DataFrame, path: str):
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    df.to_excel(path)


def make_geojson(geo_df: pd.DataFrame, features: list) -> dict:
    geojson = {"type": "FeatureCollection", "features": []}
    if 'Census Tract' in geo_df.columns:
        for i, row in geo_df.iterrows():
            feature = row['coordinates']['features'][0]
            props = {"name": str(row['Census Tract'])}
            for f in features:
                props.update({f: row[f]})
            feature["properties"] = props
            del feature["id"]
            del feature["bbox"]
            feature["geometry"]["coordinates"] = [feature["geometry"]["coordinates"]]
            geojson["features"].append(feature)
    elif 'Census Tract' not in geo_df.columns:
        for i, row in geo_df.iterrows():
            feature = row['coordinates']['features'][0]
            props = {"name": row['County Name']}
            for f in features:
                props.update({f: row[f]})
            feature["properties"] = props
            del feature["id"]
            del feature["bbox"]
            feature["geometry"]["coordinates"] = [feature["geometry"]["coordinates"]]
            geojson["features"].append(feature)
    return geojson


def convert_coordinates(row) -> list:
    for f in row['coordinates']['features']:
        new_coords = []
        if f['geometry']['type'] == 'MultiPolygon':
            f['geometry']['type'] = 'Polygon'
            combined = []
            for i in range(len(f['geometry']['coordinates'])):
                combined.extend(list(f['geometry']['coordinates'][i]))
            f['geometry']['coordinates'] = combined
        coords = f['geometry']['coordinates']
        for coord in coords:
            for point in coord:
                new_coords.append([point[0], point[1]])
        f['geometry']['coordinates'] = new_coords
    return row['coordinates']


def convert_geom(geo_df: pd.DataFrame, data_df: pd.DataFrame, map_features: list) -> dict:
    if 'tract_id' not in data_df:
        data_df = data_df[['County Name'] + map_features]
        geo_df = geo_df.merge(data_df, on='County Name')
    elif 'tract_id' in data_df:
        geo_df = data_df[['Census Tract']]
        geo_df = geo_df.merge(data_df, on='Census Tract')
    geo_df['geom'] = geo_df.apply(lambda row: row['geom'].buffer(0), axis=1)
    geo_df['coordinates'] = geo_df.apply(lambda row: gpd.GeoSeries(row['geom']).__geo_interface__, axis=1)
    geo_df['coordinates'] = geo_df.apply(lambda row: convert_coordinates(row), axis=1)
    geojson = make_geojson(geo_df, map_features)
    return geojson