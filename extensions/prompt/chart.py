PROMPT = """When generating chart, by default use plotly, if not approporiate then use pyecharts,do not use matplotlib unless user requires    
    - Pay attention to make the graph look good and correct, such as layout and sorting of data
        - When using Plotly: use plotly_white theme 
    - - Always save chart to a image file, and always print function to show the chart:
        - When using Plotly:
            import plotly
            from plotly.utils import PlotlyJSONEncoder
            fig.write_image(output_file)
            print({"type": "plotly", "config": json.loads(json.dumps(fig.to_dict(), cls=PlotlyJSONEncoder))})
            
"""