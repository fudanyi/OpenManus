PROMPT = """
When generating chart, by default use plotly, if not approporiate then use pyecharts, do not use matplotlib unless user requires.
## Chart Guidelines
    - Pay attention to make the graph look good and correct, such as layout and sorting of data
        - When using Plotly: use plotly_white theme 
    - Always save chart to a image file, no need to show the chart.
    - Always save the chat config json to a config file, exactly like below:
        from plotly.utils import PlotlyJSONEncoder
        with open(config_file, 'w') as f:
            json.dump({"type": "plotly", "config": json.loads(json.dumps(fig.to_dict(), cls=PlotlyJSONEncoder))}, f)
    - do not directly write cls=plotly.utils.PlotlyJSONEncoder(it must be imported)
"""