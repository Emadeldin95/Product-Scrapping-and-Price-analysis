import dash
from dash import Input, Output, State, ctx, dcc, dash_table, html
import dash_bootstrap_components as dbc
import threading
import pandas as pd
import asyncio
import plotly.express as px
from scraper import Scraper
from layout import create_layout

# Initialize Dash App
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
server = app.server

# Set app layout
app.layout = create_layout()

scraper = None
scraper_thread = None
data_store = []  # Holds scraped data
scraping_status = "Stopped"

def run_scraper(url, keywords):
    """Runs the scraper in a separate thread."""
    global scraper, scraping_status
    scraping_status = "Active"
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    scraper = Scraper(url, keywords)
    loop.run_until_complete(scraper.start_scraping(update_callback))
    scraping_status = "Stopped"

def update_callback(data):
    """Updates the global data store while scraping is in progress."""
    global data_store
    data_store = data

@app.callback(
    [Output("data-table", "data"), Output("status-indicator", "children"), Output("counter-indicator", "children")],
    Input("interval-component", "n_intervals"),
    Input("start-btn", "n_clicks"),
    Input("stop-btn", "n_clicks"),
    State("url-input", "value"),
    State("keyword-input", "value"),
    prevent_initial_call=True
)
def control_scraping_and_update_table(n_intervals, start, stop, url, keywords):
    """Manages the scraping process, updates the table, live status indicator, and product counter."""
    global scraper, scraper_thread, scraping_status

    triggered_id = ctx.triggered_id

    if triggered_id == "start-btn" and url:
        if not scraper_thread or not scraper_thread.is_alive():
            scraper_thread = threading.Thread(target=run_scraper, args=(url, keywords), daemon=True)
            scraper_thread.start()
            scraping_status = "Active"

    elif triggered_id == "stop-btn" and scraper:
        scraper.stop()
        scraping_status = "Stopped"

    status_text = "Scraping Active 🟢" if scraping_status == "Active" else "Scraper Stopped 🔴"
    product_count = len(data_store)
    counter_text = f"Total Products Scraped: {product_count}"

    return data_store, status_text, counter_text

@app.callback(
    Output("download-dataframe-csv", "data"),
    Input("download-btn", "n_clicks"),
    prevent_initial_call=True
)
def download_data(n_clicks):
    """Allows downloading of scraped data."""
    if data_store:
        df = pd.DataFrame(data_store)
        return dcc.send_data_frame(df.to_csv, "scraped_data.csv")

@app.callback(
    Output("analytics-content", "children"),
    Input("analytics-interval", "n_intervals"),
    prevent_initial_call=True
)
def update_analytics(n_intervals):
    """Updates the analytics tab dynamically."""
    if not data_store:
        return html.Div("No data available yet.", style={"textAlign": "center", "color": "red"})

    df = pd.DataFrame(data_store)

    # Convert prices to numbers
    df["Price"] = df["Price"].str.replace(",", "", regex=True).str.extract(r"(\d+)").astype(float)

    if df["Price"].dropna().empty:
        return html.Div("No price data available for analytics.", style={"textAlign": "center", "color": "red"})

    # Summary statistics
    lowest_price = df["Price"].min()
    highest_price = df["Price"].max()
    avg_price = df["Price"].mean()
    median_price = df["Price"].median()

    # Price Distribution Histogram
    price_hist = px.histogram(df, x="Price", nbins=20, title="Price Distribution")

    # Box Plot to show price variations
    box_plot = px.box(df, y="Price", title="Price Variability")

    # Summary Table
    summary_table = dash_table.DataTable(
        columns=[{"name": "Statistic", "id": "stat"}, {"name": "Value", "id": "value"}],
        data=[
            {"stat": "Lowest Price", "value": f"{lowest_price} EGP"},
            {"stat": "Highest Price", "value": f"{highest_price} EGP"},
            {"stat": "Average Price", "value": f"{avg_price:.2f} EGP"},
            {"stat": "Median Price", "value": f"{median_price} EGP"}
        ],
        style_table={"marginTop": "20px"}
    )

    return html.Div([
        html.H4("Price Analytics", style={"textAlign": "center", "marginBottom": "20px"}),
        dcc.Graph(figure=price_hist),
        dcc.Graph(figure=box_plot),
        summary_table
    ])

@app.callback(
    Output("tabs-content", "children"),
    Input("tabs", "value")
)
def update_tabs(selected_tab):
    """Handles switching between Data Table and Analytics."""
    if selected_tab == "table":
        return html.Div([
            dash_table.DataTable(
                id="data-table",
                columns=[
                    {"name": "Name", "id": "Name", "presentation": "markdown"},
                    {"name": "Price", "id": "Price"},
                    {"name": "Link", "id": "Link", "presentation": "markdown"}
                ],
                data=[],
                page_size=10,
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'padding': '10px'},
                style_data_conditional=[
                    {
                        'if': {'column_id': 'Name'},
                        'maxWidth': '50%',
                        'whiteSpace': 'normal',
                        'overflow': 'hidden',
                        'textOverflow': 'ellipsis'
                    }
                ]
            )
        ])
    elif selected_tab == "analytics":
        return html.Div([
            html.Div(id="analytics-content"),
            dcc.Interval(id="analytics-interval", interval=3000, n_intervals=0)  # Update analytics every 3s
        ])

if __name__ == "__main__":
    app.run_server(debug=True)
    
    
##notes:analytics tab pauses the scrapping process untill further updates