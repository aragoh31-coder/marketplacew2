from django.core.cache import cache
from django.conf import settings
from io import BytesIO
import base64
import hashlib
import json
import logging
from datetime import datetime, date
from decimal import Decimal

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.dates import DateFormatter

logger = logging.getLogger(__name__)

class ChartGenerator:
    """Thread-safe chart generator with caching."""
    
    @staticmethod
    def get_cache_key(data, chart_type):
        """Generate cache key based on data."""
        serializable_data = []
        for item in data:
            item_copy = item.copy()
            for key, value in item_copy.items():
                if isinstance(value, datetime):
                    item_copy[key] = value.isoformat()
                elif isinstance(value, date):
                    item_copy[key] = value.isoformat()
                elif isinstance(value, Decimal):
                    item_copy[key] = float(value)
                elif isinstance(value, str) and key.endswith('_date'):
                    item_copy[key] = value
            serializable_data.append(item_copy)
        
        data_str = json.dumps(serializable_data, sort_keys=True)
        data_hash = hashlib.md5(data_str.encode()).hexdigest()
        return f"chart_{chart_type}_{data_hash}"
    
    @classmethod
    def generate_chart(cls, data, key, title, chart_type='line'):
        """Generate or retrieve cached chart."""
        if not data:
            return cls._generate_empty_chart(title)
        
        cache_key = cls.get_cache_key(data, f"{key}_{title}")
        cached = cache.get(cache_key)
        
        if cached and not settings.DEBUG:
            return cached
        
        try:
            fig = Figure(figsize=(10, 5), dpi=100, facecolor='white')
            ax = fig.add_subplot(111)
            
            dates = [d.get('date') or d.get('order__created_at__date') or d.get('created_at__date') for d in data]
            values = [d.get(key, 0) for d in data]
            
            processed_dates = []
            for date_val in dates:
                if isinstance(date_val, str):
                    try:
                        from datetime import datetime
                        processed_dates.append(datetime.fromisoformat(date_val).date())
                    except (ValueError, AttributeError):
                        processed_dates.append(date_val)
                else:
                    processed_dates.append(date_val)
            dates = processed_dates
            
            if chart_type == 'line':
                ax.plot(dates, values, color='#4CAF50', linewidth=2, marker='o', markersize=4)
            elif chart_type == 'bar':
                ax.bar(dates, values, color='#4CAF50', alpha=0.8)
            
            ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Date', fontsize=12)
            ax.set_ylabel('Value', fontsize=12)
            ax.grid(True, alpha=0.3, linestyle='--')
            
            if dates and isinstance(dates[0], (datetime, datetime.date)):
                ax.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
                fig.autofmt_xdate()  # Rotate date labels
            
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            fig.tight_layout()
            
            buffer = BytesIO()
            fig.savefig(buffer, format='png', bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            buffer.seek(0)
            
            encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            plt.close(fig)
            
            cache.set(cache_key, encoded, 3600)
            
            return encoded
            
        except Exception as e:
            logger.error(f"Chart generation error: {str(e)}")
            return cls._generate_empty_chart(title)
    
    @staticmethod
    def _generate_empty_chart(title):
        """Generate a placeholder chart for when no data is available."""
        fig = Figure(figsize=(10, 5), dpi=100, facecolor='white')
        ax = fig.add_subplot(111)
        
        ax.text(0.5, 0.5, 'No data available', 
                horizontalalignment='center',
                verticalalignment='center',
                transform=ax.transAxes,
                fontsize=16,
                color='gray')
        
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.set_xticks([])
        ax.set_yticks([])
        
        buffer = BytesIO()
        fig.savefig(buffer, format='png', bbox_inches='tight', facecolor='white')
        buffer.seek(0)
        
        encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close(fig)
        
        return encoded
