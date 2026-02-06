#!/usr/bin/env python3

import pandas as pd
import numpy as np
from datetime import datetime, time, date
import argparse
import sys
from typing import Dict, List, Tuple, Set

class TradingDayFixer:
    """
    Fix QQQ trading data timestamp issues including timezone conversion,
    trading hour filtering, and special day handling.
    """
    
    def __init__(self):
        # Known half trading days (9:30 AM - 1:00 PM EST)
        self.half_days = self._generate_half_days()
        
        # Trading hour definitions (in EST/EDT)
        self.regular_start = time(9, 30)  # 9:30 AM
        self.regular_end = time(16, 0)    # 4:00 PM
        self.half_day_end = time(13, 0)   # 1:00 PM
        self.late_day_start = time(12, 0) # noon for late trading days
        
    def _generate_half_days(self) -> Set[date]:
        """Generate set of known half trading days."""
        half_days = set()
        
        # Add common half days for each year in the data range
        for year in range(2015, 2027):
            # Black Friday (day after Thanksgiving)
            thanksgiving = self._find_thanksgiving(year)
            black_friday = thanksgiving.replace(day=thanksgiving.day + 1)
            half_days.add(black_friday)
            
            # Christmas Eve (if not weekend)
            christmas_eve = date(year, 12, 24)
            if christmas_eve.weekday() < 5:  # Monday-Friday
                half_days.add(christmas_eve)
            
            # July 3rd (if not weekend)
            july_3 = date(year, 7, 3)
            if july_3.weekday() < 5:  # Monday-Friday
                half_days.add(july_3)
                
        return half_days
    
    def _find_thanksgiving(self, year: int) -> date:
        """Find Thanksgiving date (4th Thursday in November)."""
        november_1 = date(year, 11, 1)
        # Find first Thursday
        days_until_thursday = (3 - november_1.weekday()) % 7
        first_thursday = november_1.replace(day=1 + days_until_thursday)
        # 4th Thursday is 3 weeks after first Thursday
        thanksgiving = first_thursday.replace(day=first_thursday.day + 21)
        return thanksgiving
    
    def convert_timezone(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert timestamps from UTC to EST/EDT with proper DST handling.
        
        Args:
            df: DataFrame with 'time' column in UTC
            
        Returns:
            DataFrame with converted timestamps and additional time columns
        """
        print("Converting timezone from UTC to EST/EDT...")
        
        # Convert to datetime and set UTC timezone
        df['time'] = pd.to_datetime(df['time'], utc=True)
        
        # Convert to US Eastern Time (handles DST automatically)
        df['time_est'] = df['time'].dt.tz_convert('US/Eastern')
        
        # Extract time components for filtering
        df['date'] = df['time_est'].dt.date
        df['hour_est'] = df['time_est'].dt.hour
        df['minute_est'] = df['time_est'].dt.minute
        df['time_only'] = df['time_est'].dt.time
        
        # Format timestamp for output (remove timezone)
        df['time_formatted'] = df['time_est'].dt.strftime('%Y-%m-%dT%H:%M:%S')
        
        print(f"Converted {len(df)} timestamps to EST/EDT")
        return df
    
    def detect_special_days(self, df: pd.DataFrame) -> Dict[date, str]:
        """
        Detect special trading days (half days, late days, etc.).
        
        Args:
            df: DataFrame with converted timestamps
            
        Returns:
            Dictionary mapping dates to special day types
        """
        print("Detecting special trading days...")
        
        special_days = {}
        daily_stats = {}
        
        # Calculate daily statistics
        for date, group in df.groupby('date'):
            hours = sorted(group['hour_est'].unique())
            record_count = len(group)
            
            daily_stats[date] = {
                'hours': hours,
                'count': record_count,
                'start_hour': hours[0] if hours else None,
                'end_hour': hours[-1] if hours else None
            }
        
        # Detect half days (known holidays)
        for day in self.half_days:
            if day in daily_stats:
                special_days[day] = 'half_day'
        
        # Detect late trading days (no morning session)
        for date, stats in daily_stats.items():
            if date in special_days:  # Already classified
                continue
                
            # Check if missing morning hours (9-12) but has afternoon hours
            morning_hours = set(range(9, 13))  # 9 AM to 12 PM
            afternoon_hours = set(range(13, 17))  # 1 PM to 4 PM
            
            day_hours = set(stats['hours'])
            
            if not day_hours.intersection(morning_hours) and day_hours.intersection(afternoon_hours):
                special_days[date] = 'late_day'
        
        # Detect suspicious short days (possible issues)
        normal_day_count = 78  # Expected records for full day
        half_day_count = 46    # Expected records for half day
        
        for date, stats in daily_stats.items():
            if date in special_days:
                continue
                
            if stats['count'] < half_day_count - 10:  # Much shorter than half day
                special_days[date] = 'suspicious_short'
        
        print(f"Detected {len(special_days)} special days:")
        day_types = {}
        for day_type in set(special_days.values()):
            count = sum(1 for d, t in special_days.items() if t == day_type)
            day_types[day_type] = count
            print(f"  {day_type}: {count}")
        
        return special_days
    
    def filter_trading_hours(self, df: pd.DataFrame, special_days: Dict[date, str]) -> pd.DataFrame:
        """
        Filter data to appropriate trading hours based on day type.
        NOTE: Original data is already within correct trading hours (9:30 AM - 3:55 PM EST)
        Only apply special day filters for half days.
        
        Args:
            df: DataFrame with converted timestamps
            special_days: Dictionary of special days
            
        Returns:
            Filtered DataFrame
        """
        print("Applying special day filters (data already in correct trading hours)...")
        
        filtered_data = []
        
        for date, group in df.groupby('date'):
            day_type = special_days.get(date, 'regular')
            
            if day_type == 'half_day':
                # 9:30 AM - 1:00 PM for half days
                mask = (group['time_only'] >= self.regular_start) & \
                       (group['time_only'] <= self.half_day_end)
                filtered = group[mask]
                if len(filtered) == 0:
                    print(f"  Warning: No data found for half day {date}")
            else:
                # Keep all data for regular and late days (already in correct hours)
                filtered = group
            
            if len(filtered) > 0:
                filtered_data.append(filtered)
        
        result_df = pd.concat(filtered_data, ignore_index=True)
        print(f"Applied filters: {len(result_df)} records from {len(df)} original records")
        
        return result_df
    
    def generate_outputs(self, df_original: pd.DataFrame, df_filtered: pd.DataFrame, 
                        special_days: Dict[date, str]) -> None:
        """
        Generate output files and reports.
        
        Args:
            df_original: Full dataset with timezone conversion
            df_filtered: Filtered dataset
            special_days: Dictionary of special days
        """
        print("Generating output files...")
        
        # 1. All data converted to EST/EDT
        df_est = df_original[['time_formatted', 'open', 'high', 'low', 'close', 'Volume']].copy()
        df_est.columns = ['time', 'open', 'high', 'low', 'close', 'Volume']
        df_est.to_csv('output_est.csv', index=False)
        print("  Created: output_est.csv")
        
        # 2. Regular trading hours only (no special day handling)
        regular_mask = (df_original['time_only'] >= self.regular_start) & \
                      (df_original['time_only'] <= self.regular_end)
        df_regular = df_original[regular_mask][['time_formatted', 'open', 'high', 'low', 'close', 'Volume']].copy()
        df_regular.columns = ['time', 'open', 'high', 'low', 'close', 'Volume']
        df_regular.to_csv('output_regular_hours.csv', index=False)
        print("  Created: output_regular_hours.csv")
        
        # 3. Clean data with special day handling
        df_clean = df_filtered[['time_formatted', 'open', 'high', 'low', 'close', 'Volume']].copy()
        df_clean.columns = ['time', 'open', 'high', 'low', 'close', 'Volume']
        df_clean.to_csv('output_clean.csv', index=False)
        print("  Created: output_clean.csv")
        
        # 4. Special days report
        report_data = []
        for date, day_type in sorted(special_days.items()):
            report_data.append({
                'date': date,
                'type': day_type,
                'records': len(df_original[df_original['date'] == date])
            })
        
        report_df = pd.DataFrame(report_data)
        report_df.to_csv('special_days_report.csv', index=False)
        print("  Created: special_days_report.csv")
        
        # Print summary
        print(f"\nSummary:")
        print(f"  Original records: {len(df_original)}")
        print(f"  Regular hours only: {len(df_regular)}")
        print(f"  Clean with special handling: {len(df_clean)}")
        print(f"  Special days detected: {len(special_days)}")
    
    def process_file(self, input_file: str) -> None:
        """
        Main processing function.
        
        Args:
            input_file: Path to input CSV file
        """
        try:
            # Read input file
            print(f"Reading {input_file}...")
            df = pd.read_csv(input_file)
            print(f"Loaded {len(df)} records")
            
            # Phase 1: Timezone conversion
            df_converted = self.convert_timezone(df)
            
            # Phase 2: Special day detection
            special_days = self.detect_special_days(df_converted)
            
            # Phase 3: Trading hour filtering
            df_filtered = self.filter_trading_hours(df_converted, special_days)
            
            # Phase 4: Generate outputs
            self.generate_outputs(df_converted, df_filtered, special_days)
            
            print("\nProcessing completed successfully!")
            
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Fix QQQ trading data timestamps')
    parser.add_argument('input_file', help='Input CSV file with trading data')
    
    args = parser.parse_args()
    
    fixer = TradingDayFixer()
    fixer.process_file(args.input_file)

if __name__ == "__main__":
    main()
