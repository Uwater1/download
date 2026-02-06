#!/usr/bin/env python3

import pandas as pd
import argparse
import sys
from datetime import datetime

def merge_csv_files(file1_path, file2_path, output_path):
    """
    Merge two CSV files by time column.
    
    Args:
        file1_path (str): Path to first CSV file
        file2_path (str): Path to second CSV file  
        output_path (str): Path to output merged CSV file
    """
    try:
        # Read CSV files
        print(f"Reading {file1_path}...")
        df1 = pd.read_csv(file1_path)
        print(f"Reading {file2_path}...")
        df2 = pd.read_csv(file2_path)
        
        # Check if required columns exist and are exactly the same
        required_columns = ['time', 'open', 'high', 'low', 'close', 'Volume']
        
        if list(df1.columns) != list(df2.columns):
            raise ValueError(f"CSV files must have exactly the same column headers. "
                           f"File1: {list(df1.columns)}, File2: {list(df2.columns)}")
        
        for col in required_columns:
            if col not in df1.columns:
                raise ValueError(f"Required column '{col}' not found in files")
        
        # Convert time column to datetime for proper merging
        print("Converting time columns...")
        df1['time'] = pd.to_datetime(df1['time'], utc=True)
        df2['time'] = pd.to_datetime(df2['time'], utc=True)
        
        # Sort by time to ensure proper order
        df1 = df1.sort_values('time')
        df2 = df2.sort_values('time')
        
        print(f"File 1 has {len(df1)} rows")
        print(f"File 2 has {len(df2)} rows")
        
        # Combine dataframes (concatenate) instead of merge to avoid suffixes
        print("Combining data by time...")
        merged_df = pd.concat([df1, df2], ignore_index=True)
        
        print(f"Merged dataset has {len(merged_df)} rows before deduplication")
        
        # Remove completely duplicated rows
        print("Removing completely duplicated rows...")
        merged_df = merged_df.drop_duplicates()
        
        print(f"Merged dataset has {len(merged_df)} rows after deduplication")
        
        # Sort by time
        merged_df = merged_df.sort_values('time')
        
        # Convert time back to string format for output
        merged_df['time'] = merged_df['time'].dt.strftime('%Y-%m-%dT%H:%M:%S%z')
        
        # Save merged data
        print(f"Saving merged data to {output_path}...")
        merged_df.to_csv(output_path, index=False)
        
        print("Merge completed successfully!")
        print(f"Output saved to: {output_path}")
        
        # Display column names in merged file
        print("\nColumns in merged file:")
        for i, col in enumerate(merged_df.columns):
            print(f"  {i+1}. {col}")
        
        # Show overlap statistics
        duplicate_times = merged_df['time'].duplicated().sum()
        unique_times = merged_df['time'].nunique()
        completely_duplicated = (len(df1) + len(df2)) - len(merged_df)
        
        print(f"\nStatistics:")
        print(f"  Total rows before deduplication: {len(df1) + len(df2)}")
        print(f"  Total rows after deduplication: {len(merged_df)}")
        print(f"  Completely duplicated rows removed: {completely_duplicated}")
        print(f"  Unique timestamps: {unique_times}")
        print(f"  Duplicate timestamps remaining: {duplicate_times}")
        if completely_duplicated > 0:
            print(f"  Note: {completely_duplicated} completely duplicated rows were removed")
        if duplicate_times > 0:
            print(f"  Note: {duplicate_times} timestamps have different data but same time")
            
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except pd.errors.EmptyDataError:
        print("Error: One or both CSV files are empty")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Merge two CSV files by time column')
    parser.add_argument('file1', help='Path to first CSV file')
    parser.add_argument('file2', help='Path to second CSV file')
    parser.add_argument('output', help='Path to output merged CSV file')
    
    args = parser.parse_args()
    
    merge_csv_files(args.file1, args.file2, args.output)

if __name__ == "__main__":
    main()
