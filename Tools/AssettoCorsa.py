import time
import struct
import mmap
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

class AssettoCorseRaceMonitor:
    def __init__(self):
        self.previous_positions = {}
        self.driver_names = {}
        self.race_start_time = None
        self.events = []
        self.last_speed_check = {}
        
        # Shared memory structure offsets (these may need adjustment based on AC version)
        self.SHARED_MEMORY_SIZE = 1024 * 1024  # 1MB
        self.PHYSICS_OFFSET = 0
        self.GRAPHICS_OFFSET = 1024
        
    def connect_to_shared_memory(self):
        """Connect to Assetto Corsa's shared memory"""
        try:
            # Try to open shared memory (Windows)
            self.physics_map = mmap.mmap(-1, self.SHARED_MEMORY_SIZE, "Local\\acpmf_physics")
            self.graphics_map = mmap.mmap(-1, self.SHARED_MEMORY_SIZE, "Local\\acpmf_graphics")
            self.static_map = mmap.mmap(-1, self.SHARED_MEMORY_SIZE, "Local\\acpmf_static")
            return True
        except Exception as e:
            print(f"Could not connect to shared memory: {e}")
            return False
    
    def read_race_data(self):
        """Read current race data from shared memory"""
        try:
            # Read graphics data for positions and driver info
            self.graphics_map.seek(0)
            graphics_data = self.graphics_map.read(1024)
            
            # Parse basic race info (simplified structure)
            # Note: Actual AC shared memory structure is more complex
            # This is a simplified example - you may need AC SDK documentation
            
            current_positions = {}
            # Example parsing - adjust based on actual AC memory structure
            for i in range(24):  # Max 24 drivers
                offset = i * 32  # Assuming 32 bytes per driver
                if offset + 32 < len(graphics_data):
                    driver_data = struct.unpack('16s i f f', graphics_data[offset:offset+32])
                    driver_name = driver_data[0].decode('utf-8').rstrip('\x00')
                    position = driver_data[1]
                    speed = driver_data[2]
                    
                    if driver_name and position > 0:
                        current_positions[driver_name] = {
                            'position': position,
                            'speed': speed
                        }
            
            return current_positions
            
        except Exception as e:
            print(f"Error reading race data: {e}")
            return {}
    
    def detect_overtakes(self, current_positions: Dict):
        """Detect overtakes by comparing current and previous positions"""
        if not self.previous_positions:
            self.previous_positions = current_positions.copy()
            return []
        
        overtakes = []
        
        for driver, current_data in current_positions.items():
            current_pos = current_data['position']
            
            if driver in self.previous_positions:
                previous_pos = self.previous_positions[driver]['position']
                
                # Check if position improved (lower number = better position)
                if current_pos < previous_pos:
                    # Find who was overtaken
                    for other_driver, other_data in current_positions.items():
                        if (other_driver != driver and 
                            other_data['position'] == previous_pos):
                            
                            overtakes.append({
                                'type': 'overtake',
                                'overtaking_driver': driver,
                                'overtaken_driver': other_driver,
                                'new_position': current_pos
                            })
                            break
        
        self.previous_positions = current_positions.copy()
        return overtakes
    
    def detect_accidents(self, current_positions: Dict):
        """Detect accidents based on sudden speed drops or position changes"""
        accidents = []
        
        for driver, current_data in current_positions.items():
            current_speed = current_data['speed']
            current_pos = current_data['position']
            
            if driver in self.last_speed_check:
                previous_speed = self.last_speed_check[driver]
                
                # Detect sudden speed drop (potential accident)
                if previous_speed > 50 and current_speed < 10:  # km/h thresholds
                    accidents.append({
                        'type': 'accident',
                        'driver': driver,
                        'position': current_pos
                    })
            
            self.last_speed_check[driver] = current_speed
        
        return accidents
    
    def format_time(self, elapsed_seconds: float) -> str:
        """Format elapsed time as MM:SS"""
        minutes = int(elapsed_seconds // 60)
        seconds = int(elapsed_seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    def log_event(self, event: Dict, elapsed_time: float):
        """Log race event in the desired format"""
        time_str = self.format_time(elapsed_time)
        
        if event['type'] == 'overtake':
            message = f"{time_str} - Overtake! {event['overtaking_driver']} passes {event['overtaken_driver']} for P{event['new_position']}"
        elif event['type'] == 'accident':
            message = f"{time_str} - Accident! P{event['position']} {event['driver']} is involved in an accident!"
        
        print(message)
        self.events.append(message)
    
    def save_events_to_file(self, filename: str = "race_events.txt"):
        """Save all events to a text file"""
        with open(filename, 'w') as f:
            for event in self.events:
                f.write(event + '\n')
        print(f"Events saved to {filename}")
    
    def monitor_race(self, duration_minutes: int = 30):
        """Main monitoring loop"""
        if not self.connect_to_shared_memory():
            print("Failed to connect to Assetto Corsa. Make sure the game is running.")
            return
        
        print("Connected to Assetto Corsa. Starting race monitoring...")
        self.race_start_time = time.time()
        
        try:
            while True:
                current_time = time.time()
                elapsed_time = current_time - self.race_start_time
                
                # Stop after specified duration
                if elapsed_time > duration_minutes * 60:
                    break
                
                # Read current race data
                current_positions = self.read_race_data()
                
                if current_positions:
                    # Detect and log overtakes
                    overtakes = self.detect_overtakes(current_positions)
                    for overtake in overtakes:
                        self.log_event(overtake, elapsed_time)
                    
                    # Detect and log accidents
                    accidents = self.detect_accidents(current_positions)
                    for accident in accidents:
                        self.log_event(accident, elapsed_time)
                
                # Small delay to avoid excessive CPU usage
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user.")
        
        finally:
            self.save_events_to_file()

# Alternative approach using log file monitoring
class AssettoCorseLogMonitor:
    """Monitor AC log files for race events (alternative approach)"""
    
    def __init__(self, log_path: str = None):
        self.log_path = log_path or self.find_ac_log_path()
        self.events = []
        
    def find_ac_log_path(self) -> str:
        """Try to find AC log directory"""
        possible_paths = [
            os.path.expanduser("~/Documents/Assetto Corsa/logs"),
            "C:\\Program Files (x86)\\Steam\\steamapps\\common\\assettocorsa\\logs",
            "./logs"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return "./logs"  # Default fallback
    
    def parse_log_line(self, line: str, timestamp: float) -> Optional[Dict]:
        """Parse a log line for race events"""
        # This would need to be customized based on AC's actual log format
        if "COLLISION" in line.upper():
            # Extract driver name and position from collision log
            return {'type': 'accident', 'raw_line': line}
        elif "POSITION" in line.upper():
            # Extract position change information
            return {'type': 'position_change', 'raw_line': line}
        
        return None
    
    def monitor_logs(self):
        """Monitor AC log files for events"""
        print(f"Monitoring logs in: {self.log_path}")
        # Implementation would depend on AC's log file format
        pass

# Example usage and setup
def main():
    print("Assetto Corsa Race Event Monitor")
    print("Choose monitoring method:")
    print("1. Shared Memory (Real-time, requires AC running)")
    print("2. Log File (Post-race analysis)")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        monitor = AssettoCorseRaceMonitor()
        duration = int(input("Enter race duration in minutes (default 30): ") or "30")
        monitor.monitor_race(duration)
    
    elif choice == "2":
        log_path = input("Enter AC logs directory (press Enter for auto-detect): ").strip()
        monitor = AssettoCorseLogMonitor(log_path if log_path else None)
        monitor.monitor_logs()
    
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    main()