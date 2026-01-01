from abc import ABC, abstractmethod
import pandas as pd

class BaseStrategy(ABC):
    def __init__(self, name, capital=100.0):
        self.name = name
        self.capital = capital

    @abstractmethod
    def run(self, df):
        """
        Runs the strategy on the provided DataFrame.
        Returns: (roi_pct, equity_curve_series)
        """
        pass
