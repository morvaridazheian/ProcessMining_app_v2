from datetime import datetime, timedelta
import random
import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, dash_table
from flask import Flask, send_file
import base64
import io
import os  # Import for dynamic port setting
import networkx as nx
import matplotlib.pyplot as plt

# =============== Generate a Simple Event Log for Testing =============== #
def generate_sample_event_log():
    cases = [f"Case_{i}" for i in range(1, 6)]  # 5 cases
    activities = ["Start", "Review", "Approve", "End"]
    data = []

    for case in cases:
        start_time = datetime.now() - timedelta(days=random.randint(1, 30))
        for activity in activities:
            data.append({
                "case_id": case,
                "activity": activity,
                "timestamp": start_time.strftime("%Y-%m-%d %H:%M:%S")
            })
            start_time += timedelta(minutes=random.randint(5, 60))  # Random delay

    return pd.DataFrame(data)

# =============== Data Validation Function =============== #
def validate_data(df):
    """Validates the uploaded data for required columns and correct timestamp format."""
    try:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    except Exception as e:
        raise ValueError(f"Timestamp column conversion failed: {str(e)}")

    if df[['activity', 'case_id', 'timestamp']].isnull().any().any():
        raise ValueError("Missing values in required columns: 'activity', 'case_id', or 'timestamp'")

    return df

# =============== Decode File Function =============== #
def decode_file(contents):
    """Decodes uploaded CSV file."""
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    return io.StringIO(decoded.decode('utf-8'))

# Generate sample event log
event_log = generate_sample_event_log()

# =============== Flask + Dash App Setup =============== #
server = Flask(__name__)  # Flask app
app = Dash(__name__, server=server)  # Dash app inside Flask

# =============== Dash Layout (User Interface) =============== #
app.layout = html.Div([
    html.H1("Process Mining Dashboard", style={'textAlign': 'center'}),
    dcc.Upload(id='upload-data', children=html.Button('Upload CSV File'), multiple=False),
    html.Hr(),
    html.Div(id='data-overview'),
    html.Hr(),
    dcc.Tabs([
        dcc.Tab(label='Process Bottlenecks', children=[dcc.Graph(id='bottleneck-graph')]),
        dcc.Tab(label='Process Loops', children=[html.Img(id='loop-graph')]),
        dcc.Tab(label='Process Variants', children=[html.Div(id='variant-summary')]),
        dcc.Tab(label='Compliance Analysis', children=[html.Div(id='compliance-summary')])
    ])
])

# =============== Callbacks =============== #

# ---- Process Loops Visualization ---- #
@app.callback(Output('loop-graph', 'src'), Input('upload-data', 'contents'))
def visualize_loops(contents):
    """Generates a directed graph visualization of process loops."""
    df = event_log if contents is None else pd.read_csv(decode_file(contents))

    try:
        df = validate_data(df)
    except ValueError as e:
        return None

    df = df.sort_values(by=['case_id', 'timestamp'])
    G = nx.DiGraph()

    for _, group in df.groupby('case_id'):
        activities = group['activity'].tolist()
        for i in range(len(activities) - 1):
            G.add_edge(activities[i], activities[i + 1])

    # Generate the plot and save it to an in-memory buffer
    fig, ax = plt.subplots(figsize=(6, 4))
    pos = nx.spring_layout(G)
    nx.draw(G, pos, with_labels=True, node_color='lightblue', edge_color='gray', node_size=2000, font_size=10, ax=ax)
    
    # Save the plot to a buffer and encode it as base64
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png')
    img_buf.seek(0)
    img_base64 = base64.b64encode(img_buf.read()).decode('utf-8')
    img_buf.close()

    return f"data:image/png;base64,{img_base64}"

# ---- Process Bottlenecks ---- #
@app.callback(Output('bottleneck-graph', 'figure'), Input('upload-data', 'contents'))
def detect_bottlenecks(contents):
    """Detects bottlenecks by calculating average time spent per activity."""
    df = event_log if contents is None else pd.read_csv(decode_file(contents))
    try:
        df = validate_data(df)
    except ValueError as e:
        return px.bar([], x=[], y=[], title=f"Error: {str(e)}")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['time_diff'] = df.groupby('case_id')['timestamp'].diff().dt.total_seconds()
    df['time_diff_minutes'] = df['time_diff'] / 60
    avg_times = df.groupby('activity')['time_diff_minutes'].mean().reset_index()
    return px.bar(avg_times, x='activity', y='time_diff_minutes', title="Average Time Spent Per Activity")

# ---- Process Variants ---- #
@app.callback(Output('variant-summary', 'children'), Input('upload-data', 'contents'))
def analyze_variants(contents):
    """Analyzes process variants by extracting unique activity sequences."""
    df = event_log if contents is None else pd.read_csv(decode_file(contents))
    try:
        df = validate_data(df)
    except ValueError as e:
        return html.Div([html.H3(f"Error: {str(e)}")])
    df = df.sort_values(by=['case_id', 'timestamp'])
    variant_series = df.groupby('case_id')['activity'].apply(tuple)
    variant_counts = variant_series.value_counts().reset_index()
    variant_counts.columns = ['Process Variant', 'Count']
    if variant_counts.empty:
        return html.Div([html.H3("No Process Variants Found")])
    top_10_variants = variant_counts.head(10)
    return html.Div([html.H3("Top 10 Process Variants")] + [html.P(f"Variant {idx + 1}: {' → '.join(row['Process Variant'])} (Count: {row['Count']})") for idx, row in top_10_variants.iterrows()])

# =============== Run the App =============== #
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8050))  # Correcting the port to use dynamic environment variable
    app.run_server(debug=True, port=port, host='0.0.0.0')
