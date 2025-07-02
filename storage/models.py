from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import pandas as pd

class DatasetResult(BaseModel):
    score: Optional[float] = Field(None, description="Full-text search score (BM25)", example=12.34)
    id: str = Field(..., description="Dataset unique identifier", example="reanalysis-era5-single-levels")
    rel_link: Optional[str] = Field(None, description="Relative link to the dataset page", example="/datasets/reanalysis-era5-single-levels?tab=overview")
    abs_link: Optional[str] = Field(None, description="Absolute link to the dataset page", example="https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels")
    title: Optional[str] = Field(None, description="Dataset title", example="ERA5 hourly data on single levels from 1940 to present")
    description: Optional[str] = Field(None, description="Dataset description", example="ERA5 is the fifth generation ECMWF reanalysis for the global climate and weather for the past 8 decades.")
    tags: Optional[str] = Field(None, description="Tags or categories for the dataset", example="Reanalysis, Copernicus C3S, Global, Past, Atmosphere (surface)")
    created_at: Optional[datetime] = Field(None, description="Timestamp when the dataset was added", example="2024-06-17T12:34:56.789Z")
    updated_at: Optional[datetime] = Field(None, description="Timestamp when the dataset was last updated", example="2024-06-17T12:34:56.789Z")

    def model_dump_csv(self, index: bool = False, sep: str = ",", header: bool = False) -> str:
        """Convert the model to CSV format string."""
        # Convert model to dict and create DataFrame
        data = self.model_dump()
        df = pd.DataFrame([data])
        
        # Convert to CSV string
        csv_string = df.to_csv(index=index, sep=sep, header=header)
        return csv_string

    def model_dump_tsv(self, index: bool = False, header: bool = False) -> str:
        """Convert the model to TSV format string."""
        return self.model_dump_csv(index=index, sep="\t", header=header)