"""Graph generation tool for creating visualizations from data."""

import asyncio
import base64
import io
import json
import logging
import tempfile
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
from mcp.server.fastmcp import Context
from pydantic import Field

from ..config import get_postgres_url
from ..models.connection import Connection
from ..models.query import Query
from ..utils import serialize_response

# Set matplotlib backend for headless operation
matplotlib.use('Agg')

__all__ = ["generate_graph"]


class GraphType(str, Enum):
    """Supported graph types."""
    LINE = "line"
    BAR = "bar"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    BOX = "box"
    VIOLIN = "violin"
    HEATMAP = "heatmap"
    PIE = "pie"
    AREA = "area"
    REGRESSION = "regression"


class OutputFormat(str, Enum):
    """Supported output formats."""
    BASE64 = "base64"
    HTML = "html"
    JSON = "json"


async def _get_context_field(field: str, ctx: Context) -> Any:
    """Get the context of the current request."""
    return getattr(getattr(getattr(ctx, "request_context", None), "lifespan_context", None), field, None)


async def _execute_query_if_needed(ctx: Context, data_source: str) -> pd.DataFrame:
    """Execute a SQL query if data_source is a query, otherwise treat as table name."""
    logger = logging.getLogger("blitz-agent-mcp")
    
    # Check if it looks like a SQL query
    if any(keyword in data_source.upper() for keyword in ['SELECT', 'FROM', 'WHERE', 'JOIN']):
        # It's a SQL query, execute it
        postgres_url = get_postgres_url()
        if not postgres_url:
            raise ConnectionError("PostgreSQL configuration is incomplete. Please configure PostgreSQL settings.")
        
        query_obj = Query(code=data_source, description="Graph data query")
        query_obj.connection = Connection(url=postgres_url)
        
        url_map = await _get_context_field("url_map", ctx)
        db = await query_obj.connection.connect(url_map=url_map)
        result = await db.query(code=query_obj.code)
        
        # Convert result to DataFrame
        if isinstance(result, dict) and 'data' in result:
            # Handle table format
            columns = result['data']['columns']
            rows = result['data']['rows']
            df = pd.DataFrame(rows, columns=columns)
            # Remove index column if present
            if 'index' in df.columns:
                df = df.drop('index', axis=1)
        else:
            df = pd.DataFrame(result)
    else:
        # Treat as table name and sample it
        from tools.sample import sample
        result = await sample(ctx, table=data_source, n=1000)  # Get more rows for graphing
        
        # Convert to DataFrame
        if isinstance(result, dict) and 'data' in result:
            columns = result['data']['columns']
            rows = result['data']['rows']
            df = pd.DataFrame(rows, columns=columns)
            # Remove index column if present
            if 'index' in df.columns:
                df = df.drop('index', axis=1)
        else:
            df = pd.DataFrame(result)
    
    return df


def _create_matplotlib_plot(
    df: pd.DataFrame,
    graph_type: GraphType,
    x_column: Optional[str],
    y_column: Optional[str],
    title: str,
    width: int,
    height: int,
    **kwargs
) -> str:
    """Create a matplotlib/seaborn plot and return as base64."""
    plt.figure(figsize=(width/100, height/100))
    
    if graph_type == GraphType.LINE:
        if x_column and y_column:
            plt.plot(df[x_column], df[y_column], **kwargs)
        else:
            df.plot(kind='line', **kwargs)
    
    elif graph_type == GraphType.BAR:
        if x_column and y_column:
            plt.bar(df[x_column], df[y_column], **kwargs)
        else:
            df.plot(kind='bar', **kwargs)
    
    elif graph_type == GraphType.SCATTER:
        if x_column and y_column:
            plt.scatter(df[x_column], df[y_column], **kwargs)
        else:
            # Use first two numeric columns
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if len(numeric_cols) >= 2:
                plt.scatter(df[numeric_cols[0]], df[numeric_cols[1]], **kwargs)
    
    elif graph_type == GraphType.HISTOGRAM:
        if y_column:
            plt.hist(df[y_column], **kwargs)
        else:
            # Use first numeric column
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if numeric_cols:
                plt.hist(df[numeric_cols[0]], **kwargs)
    
    elif graph_type == GraphType.BOX:
        if y_column:
            sns.boxplot(data=df, y=y_column, **kwargs)
        else:
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if numeric_cols:
                sns.boxplot(data=df[numeric_cols], **kwargs)
    
    elif graph_type == GraphType.VIOLIN:
        if y_column:
            sns.violinplot(data=df, y=y_column, **kwargs)
        else:
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if numeric_cols:
                sns.violinplot(data=df[numeric_cols], **kwargs)
    
    elif graph_type == GraphType.HEATMAP:
        # Create correlation heatmap for numeric columns
        numeric_df = df.select_dtypes(include=['number'])
        if not numeric_df.empty:
            correlation = numeric_df.corr()
            sns.heatmap(correlation, annot=True, cmap='coolwarm', center=0, **kwargs)
    
    elif graph_type == GraphType.PIE:
        if x_column and y_column:
            plt.pie(df[y_column], labels=df[x_column], **kwargs)
        else:
            # Use first two columns
            if len(df.columns) >= 2:
                plt.pie(df.iloc[:, 1], labels=df.iloc[:, 0], **kwargs)
    
    elif graph_type == GraphType.AREA:
        if x_column and y_column:
            plt.fill_between(df[x_column], df[y_column], **kwargs)
        else:
            df.plot(kind='area', **kwargs)
    
    elif graph_type == GraphType.REGRESSION:
        if x_column and y_column:
            sns.regplot(data=df, x=x_column, y=y_column, **kwargs)
        else:
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if len(numeric_cols) >= 2:
                sns.regplot(data=df, x=numeric_cols[0], y=numeric_cols[1], **kwargs)
    
    plt.title(title)
    plt.tight_layout()
    
    # Save to base64
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode()
    plt.close()
    
    return image_base64


def _create_plotly_plot(
    df: pd.DataFrame,
    graph_type: GraphType,
    x_column: Optional[str],
    y_column: Optional[str],
    title: str,
    width: int,
    height: int,
    **kwargs
) -> Union[str, Dict]:
    """Create a plotly plot and return as HTML or JSON."""
    fig = None
    
    if graph_type == GraphType.LINE:
        if x_column and y_column:
            fig = px.line(df, x=x_column, y=y_column, title=title, **kwargs)
        else:
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if numeric_cols:
                fig = px.line(df, y=numeric_cols, title=title, **kwargs)
    
    elif graph_type == GraphType.BAR:
        if x_column and y_column:
            fig = px.bar(df, x=x_column, y=y_column, title=title, **kwargs)
        else:
            # Use first categorical and first numeric column
            cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
            num_cols = df.select_dtypes(include=['number']).columns.tolist()
            if cat_cols and num_cols:
                fig = px.bar(df, x=cat_cols[0], y=num_cols[0], title=title, **kwargs)
    
    elif graph_type == GraphType.SCATTER:
        if x_column and y_column:
            fig = px.scatter(df, x=x_column, y=y_column, title=title, **kwargs)
        else:
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if len(numeric_cols) >= 2:
                fig = px.scatter(df, x=numeric_cols[0], y=numeric_cols[1], title=title, **kwargs)
    
    elif graph_type == GraphType.HISTOGRAM:
        if y_column:
            fig = px.histogram(df, x=y_column, title=title, **kwargs)
        else:
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if numeric_cols:
                fig = px.histogram(df, x=numeric_cols[0], title=title, **kwargs)
    
    elif graph_type == GraphType.BOX:
        if y_column:
            fig = px.box(df, y=y_column, title=title, **kwargs)
        else:
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if numeric_cols:
                fig = px.box(df, y=numeric_cols, title=title, **kwargs)
    
    elif graph_type == GraphType.VIOLIN:
        if y_column:
            fig = px.violin(df, y=y_column, title=title, **kwargs)
        else:
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if numeric_cols:
                fig = px.violin(df, y=numeric_cols[0], title=title, **kwargs)
    
    elif graph_type == GraphType.HEATMAP:
        numeric_df = df.select_dtypes(include=['number'])
        if not numeric_df.empty:
            correlation = numeric_df.corr()
            fig = px.imshow(correlation, text_auto=True, title=title, **kwargs)
    
    elif graph_type == GraphType.PIE:
        if x_column and y_column:
            fig = px.pie(df, names=x_column, values=y_column, title=title, **kwargs)
        else:
            if len(df.columns) >= 2:
                fig = px.pie(df, names=df.columns[0], values=df.columns[1], title=title, **kwargs)
    
    elif graph_type == GraphType.AREA:
        if x_column and y_column:
            fig = px.area(df, x=x_column, y=y_column, title=title, **kwargs)
        else:
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if len(numeric_cols) >= 2:
                fig = px.area(df, x=df.index, y=numeric_cols[0], title=title, **kwargs)
    
    elif graph_type == GraphType.REGRESSION:
        if x_column and y_column:
            fig = px.scatter(df, x=x_column, y=y_column, title=title, trendline="ols", **kwargs)
        else:
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if len(numeric_cols) >= 2:
                fig = px.scatter(df, x=numeric_cols[0], y=numeric_cols[1], title=title, trendline="ols", **kwargs)
    
    if fig:
        fig.update_layout(width=width, height=height)
        return fig
    
    return None


async def generate_graph(
    ctx: Context,
    data_source: str = Field(..., description="SQL query or table name to get data from"),
    graph_type: GraphType = Field(GraphType.LINE, description="Type of graph to generate"),
    x_column: Optional[str] = Field(None, description="Column name for X-axis (if applicable)"),
    y_column: Optional[str] = Field(None, description="Column name for Y-axis (if applicable)"),
    title: str = Field("Generated Graph", description="Title for the graph"),
    output_format: OutputFormat = Field(OutputFormat.BASE64, description="Output format for the graph"),
    width: int = Field(800, description="Width of the graph in pixels", ge=200, le=2000),
    height: int = Field(600, description="Height of the graph in pixels", ge=200, le=2000),
    color_palette: Optional[str] = Field("Set1", description="Color palette for the graph"),
) -> Dict[str, Any]:
    """
    Generate various types of graphs and charts from database data.
    
    Graph Types Available:
    - line: Line chart for time series or continuous data
    - bar: Bar chart for categorical data
    - scatter: Scatter plot for correlation analysis
    - histogram: Distribution of numeric data
    - box: Box plot for statistical summaries
    - violin: Violin plot for distribution shape
    - heatmap: Correlation heatmap for numeric data
    - pie: Pie chart for proportional data
    - area: Area chart for cumulative data
    - regression: Scatter plot with regression line
    
    Output Formats:
    - base64: PNG image encoded as base64 string
    - html: Interactive HTML plot (using Plotly)
    - json: Plot configuration as JSON
    
    Usage Tips:
    1. For time series data, use line or area charts
    2. For categorical comparisons, use bar charts
    3. For correlation analysis, use scatter or heatmap
    4. For distribution analysis, use histogram, box, or violin plots
    5. Specify x_column and y_column for better control
    6. If columns aren't specified, the tool will auto-select appropriate columns
    """
    logger = logging.getLogger("blitz-agent-mcp")
    
    try:
        # Get data from query or table
        df = await _execute_query_if_needed(ctx, data_source)
        
        if df.empty:
            raise ValueError("No data available from the specified source")
        
        logger.info(f"Creating {graph_type} graph with {len(df)} rows of data")
        
        # Create the graph based on output format
        if output_format == OutputFormat.BASE64:
            # Use matplotlib/seaborn for static images
            image_base64 = _create_matplotlib_plot(
                df, graph_type, x_column, y_column, title, width, height,
                palette=color_palette if color_palette else None
            )
            
            return {
                "graph_type": graph_type,
                "format": "base64_png",
                "image": image_base64,
                "width": width,
                "height": height,
                "data_rows": len(df),
                "title": title
            }
        
        elif output_format in [OutputFormat.HTML, OutputFormat.JSON]:
            # Use plotly for interactive plots
            fig = _create_plotly_plot(
                df, graph_type, x_column, y_column, title, width, height,
                color_discrete_sequence=px.colors.qualitative.Set1 if color_palette == "Set1" else None
            )
            
            if fig is None:
                raise ValueError(f"Could not create {graph_type} plot with the provided data")
            
            if output_format == OutputFormat.HTML:
                html_content = fig.to_html(include_plotlyjs=True, div_id="graph")
                return {
                    "graph_type": graph_type,
                    "format": "html",
                    "html": html_content,
                    "width": width,
                    "height": height,
                    "data_rows": len(df),
                    "title": title
                }
            
            else:  # JSON format
                return {
                    "graph_type": graph_type,
                    "format": "json",
                    "plotly_json": fig.to_dict(),
                    "width": width,
                    "height": height,
                    "data_rows": len(df),
                    "title": title
                }
        
    except Exception as e:
        logger.error(f"Failed to generate graph: {str(e)}")
        raise RuntimeError(f"Graph generation failed: {str(e)}") 