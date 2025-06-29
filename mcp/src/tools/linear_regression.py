"""Linear regression analysis tool for statistical modeling and prediction."""

import asyncio
import base64
import io
import json
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from mcp.server.fastmcp import Context
from pydantic import Field
from scipy import stats
from sklearn.linear_model import LinearRegression, Ridge, Lasso, ElasticNet
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, PolynomialFeatures

from config import get_postgres_url
from models.connection import Connection
from models.query import Query
from utils import serialize_response

# Set matplotlib backend for headless operation
matplotlib.use('Agg')

__all__ = ["run_linear_regression"]


class RegressionType(str, Enum):
    """Supported regression types."""
    SIMPLE = "simple"
    MULTIPLE = "multiple"
    POLYNOMIAL = "polynomial"
    RIDGE = "ridge"
    LASSO = "lasso"
    ELASTIC_NET = "elastic_net"


class ValidationMethod(str, Enum):
    """Model validation methods."""
    TRAIN_TEST = "train_test"
    CROSS_VAL = "cross_validation"
    NONE = "none"


async def _get_context_field(field: str, ctx: Context) -> Any:
    """Get the context of the current request."""
    return getattr(getattr(getattr(ctx, "request_context", None), "lifespan_context", None), field, None)


async def run_linear_regression(
    ctx: Context,
    data_source: str = Field(..., description="SQL query or table name to get data from"),
    target_column: str = Field(..., description="Name of the target variable (dependent variable)"),
    feature_columns: Optional[List[str]] = Field(None, description="List of feature column names. If None, all numeric columns except target will be used"),
    regression_type: RegressionType = Field(RegressionType.MULTIPLE, description="Type of regression to perform"),
    validation_method: ValidationMethod = Field(ValidationMethod.TRAIN_TEST, description="Model validation method"),
    polynomial_degree: int = Field(1, description="Degree for polynomial regression", ge=1, le=5),
    alpha: float = Field(1.0, description="Regularization strength for Ridge/Lasso/ElasticNet", gt=0),
    l1_ratio: float = Field(0.5, description="L1 ratio for ElasticNet", ge=0, le=1),
    test_size: float = Field(0.2, description="Proportion of data for testing", gt=0, lt=1),
    cv_folds: int = Field(5, description="Number of folds for cross-validation", ge=2, le=10),
    include_plots: bool = Field(True, description="Whether to include diagnostic plots"),
    standardize_features: bool = Field(False, description="Whether to standardize features")
) -> Dict[str, Any]:
    """
    Perform comprehensive linear regression analysis on database data.
    
    Regression Types:
    - simple: Simple linear regression (one predictor variable)
    - multiple: Multiple linear regression (multiple predictors)
    - polynomial: Polynomial regression (with degree specification)
    - ridge: Ridge regression with L2 regularization
    - lasso: Lasso regression with L1 regularization
    - elastic_net: Elastic Net regression with both L1 and L2 regularization
    
    Validation Methods:
    - train_test: Split data into training and testing sets
    - cross_validation: K-fold cross-validation
    - none: No validation (use all data for training)
    
    Output includes:
    - Model coefficients and statistics
    - R-squared, MSE, RMSE, MAE
    - Residual analysis
    - Model validation results
    - Diagnostic plots (optional)
    """
    logger = logging.getLogger("blitz-agent-mcp")
    
    try:
        # Get data from query or table
        if any(keyword in data_source.upper() for keyword in ['SELECT', 'FROM', 'WHERE', 'JOIN']):
            # Execute SQL query
            postgres_url = get_postgres_url()
            if not postgres_url:
                raise ConnectionError("PostgreSQL configuration is incomplete")
            
            query_obj = Query(code=data_source, description="Regression data query")
            query_obj.connection = Connection(url=postgres_url)
            
            url_map = await _get_context_field("url_map", ctx)
            db = await query_obj.connection.connect(url_map=url_map)
            result = await db.query(code=query_obj.code)
            
            if isinstance(result, dict) and 'data' in result:
                columns = result['data']['columns']
                rows = result['data']['rows']
                df = pd.DataFrame(rows, columns=columns)
                if 'index' in df.columns:
                    df = df.drop('index', axis=1)
            else:
                df = pd.DataFrame(result)
        else:
            # Sample from table
            from tools.sample import sample
            result = await sample(ctx, table=data_source, n=1000)
            
            if isinstance(result, dict) and 'data' in result:
                columns = result['data']['columns']
                rows = result['data']['rows']
                df = pd.DataFrame(rows, columns=columns)
                if 'index' in df.columns:
                    df = df.drop('index', axis=1)
            else:
                df = pd.DataFrame(result)
        
        if df.empty:
            raise ValueError("No data available from the specified source")
        
        # Validate target column
        if target_column not in df.columns:
            raise ValueError(f"Target column '{target_column}' not found in data")
        
        # Prepare features
        if feature_columns is None:
            feature_columns = [col for col in df.select_dtypes(include=[np.number]).columns 
                             if col != target_column]
        
        if not feature_columns:
            raise ValueError("No numeric feature columns found")
        
        # Create feature matrix and target vector
        X_df = df[feature_columns].fillna(df[feature_columns].mean())
        y_series = df[target_column].fillna(df[target_column].mean())
        
        X = X_df.values
        y = y_series.values
        
        # Apply polynomial features if requested
        if polynomial_degree > 1:
            poly = PolynomialFeatures(degree=polynomial_degree, include_bias=False)
            X = poly.fit_transform(X)
            feature_names = list(poly.get_feature_names_out(feature_columns))
        else:
            feature_names = feature_columns
        
        # Standardize features if requested
        if standardize_features:
            scaler = StandardScaler()
            X = scaler.fit_transform(X)
        
        # Choose regression model
        if regression_type == RegressionType.RIDGE:
            model = Ridge(alpha=alpha)
        elif regression_type == RegressionType.LASSO:
            model = Lasso(alpha=alpha)
        elif regression_type == RegressionType.ELASTIC_NET:
            model = ElasticNet(alpha=alpha, l1_ratio=l1_ratio)
        else:
            model = LinearRegression()
        
        # Fit model
        model.fit(X, y)
        y_pred = model.predict(X)
        
        # Calculate metrics
        r2 = r2_score(y, y_pred)
        mse = mean_squared_error(y, y_pred)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y, y_pred)
        
        # Adjusted R²
        n = len(y)
        p = X.shape[1]
        adj_r2 = 1 - (1 - r2) * (n - 1) / (n - p - 1) if n > p + 1 else r2
        
        # Residuals
        residuals = y - y_pred
        
        # Model coefficients
        coefficients = {'intercept': float(model.intercept_)}
        for i, coef in enumerate(model.coef_):
            feature_name = feature_names[i] if i < len(feature_names) else f"feature_{i}"
            coefficients[feature_name] = float(coef)
        
        # Prepare response
        response = {
            "regression_type": regression_type,
            "target_variable": target_column,
            "feature_variables": feature_names,
            "data_info": {
                "total_samples": len(df),
                "features_count": len(feature_names)
            },
            "model_metrics": {
                "r_squared": float(r2),
                "adjusted_r_squared": float(adj_r2),
                "mean_squared_error": float(mse),
                "root_mean_squared_error": float(rmse),
                "mean_absolute_error": float(mae)
            },
            "coefficients": coefficients,
            "residual_analysis": {
                "mean": float(np.mean(residuals)),
                "std": float(np.std(residuals)),
                "min": float(np.min(residuals)),
                "max": float(np.max(residuals))
            }
        }
        
        # Validation
        if validation_method == ValidationMethod.TRAIN_TEST:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=42
            )
            model_val = type(model)(**model.get_params())
            model_val.fit(X_train, y_train)
            y_test_pred = model_val.predict(X_test)
            
            response["validation"] = {
                "test_r2": float(r2_score(y_test, y_test_pred)),
                "test_mse": float(mean_squared_error(y_test, y_test_pred)),
                "test_rmse": float(np.sqrt(mean_squared_error(y_test, y_test_pred)))
            }
        
        elif validation_method == ValidationMethod.CROSS_VAL:
            cv_scores = cross_val_score(model, X, y, cv=cv_folds, scoring='r2')
            response["validation"] = {
                "cv_r2_mean": float(np.mean(cv_scores)),
                "cv_r2_std": float(np.std(cv_scores)),
                "cv_scores": cv_scores.tolist()
            }
        
        # Create diagnostic plots
        if include_plots:
            fig, axes = plt.subplots(2, 2, figsize=(12, 10))
            fig.suptitle('Regression Diagnostic Plots', fontsize=16)
            
            # Actual vs Predicted
            axes[0, 0].scatter(y, y_pred, alpha=0.6)
            axes[0, 0].plot([y.min(), y.max()], [y.min(), y.max()], 'r--', lw=2)
            axes[0, 0].set_xlabel(f'Actual {target_column}')
            axes[0, 0].set_ylabel(f'Predicted {target_column}')
            axes[0, 0].set_title('Actual vs Predicted')
            
            # Residuals vs Predicted
            axes[0, 1].scatter(y_pred, residuals, alpha=0.6)
            axes[0, 1].axhline(y=0, color='r', linestyle='--')
            axes[0, 1].set_xlabel(f'Predicted {target_column}')
            axes[0, 1].set_ylabel('Residuals')
            axes[0, 1].set_title('Residuals vs Predicted')
            
            # Q-Q plot
            stats.probplot(residuals, dist="norm", plot=axes[1, 0])
            axes[1, 0].set_title('Q-Q Plot of Residuals')
            
            # Histogram of residuals
            axes[1, 1].hist(residuals, bins=20, edgecolor='black', alpha=0.7)
            axes[1, 1].set_xlabel('Residuals')
            axes[1, 1].set_ylabel('Frequency')
            axes[1, 1].set_title('Histogram of Residuals')
            
            plt.tight_layout()
            
            # Save to base64
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            
            response["diagnostic_plots"] = {
                "format": "base64_png",
                "image": image_base64
            }
        
        # Create regression equation
        equation_parts = [f"{coefficients['intercept']:.4f}"]
        for feature in feature_names:
            coef = coefficients.get(feature, 0)
            if coef >= 0:
                equation_parts.append(f" + {coef:.4f}*{feature}")
            else:
                equation_parts.append(f" - {abs(coef):.4f}*{feature}")
        
        response["regression_equation"] = f"{target_column} = {''.join(equation_parts)}"
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to perform regression analysis: {str(e)}")
        raise RuntimeError(f"Regression analysis failed: {str(e)}") 