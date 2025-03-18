import sys
import os
import pprint
from datetime import datetime
from accapi.client import AccClient


class AccidentMonitor:
    def __init__(self):
        self.client = AccClient()
        self.current_accidents = {}
        self.session_time_ms = 0
        self.cars = {}
        self.output_file = None
        self.running = True

    def setup_client(self):
        """Setup the ACC client and subscribe to necessary events"""
        self.client.onRealtimeUpdate.subscribe(self.on_realtime_update)
        self.client.onRealtimeCarUpdate.subscribe(self.on_realtime_car_update)
        self.client.onEntryListCarUpdate.subscribe(self.on_entry_list_car_update)
        self.client.onBroadcastingEvent.subscribe(self.on_broadcasting_event)

    def start_client(self):
        """Start the ACC client connection"""
        self.client.start(
            url="localhost",
            port=9000,
            password="asd",
            commandPassword="",
            displayName="ACC Accident Monitor",
            updateIntervalMs=100
        )

    def setup_output_file(self):
        """Setup the output file for logging accidents"""
        try:
            if not os.path.exists("Accident Data"):
                os.makedirs("Accident Data")

            start_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.output_file = os.path.join("Accident Data", f"accidents_{start_time}.txt")

            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(f"ACC Accident Monitoring started at: {start_time}\n\n")

            print(f"Logging accidents to: {self.output_file}")

        except Exception as e:
            print(f"Error setting up output file: {e}")
            sys.exit(1)

    def on_realtime_update(self, event):
        """Handle realtime updates to track session time"""
        self.session_time_ms = event.content.sessionTimeMs

    def on_realtime_car_update(self, event):
        """Handle realtime car updates"""
        car = event.content
        if car.carIndex not in self.cars:
            self.cars[car.carIndex] = {
                'carIndex': car.carIndex,
                'driverName': f'Car {car.carIndex}'
            }

    def on_entry_list_car_update(self, event):
        """Handle driver information updates"""
        car = event.content
        if car.carIndex not in self.cars:
            self.cars[car.carIndex] = {'carIndex': car.carIndex}

        if car.drivers:
            driver = car.drivers[0]
            self.cars[car.carIndex]['driverName'] = f"{driver.firstName} {driver.lastName}"

    def on_broadcasting_event(self, event):
        """Handle broadcasting events, specifically accidents"""
        event_content = event.content
        if event_content.type == "Accident":
            self.handle_accident(event_content, event)

    def handle_accident(self, event_content, full_event):
        """
        Process and log accident events using the accident event’s own timeMs for timestamping,
        and output the full unparsed data.
        """
        # Use the accident event's own timeMs for logging
        accident_time = self.format_time(event_content.timeMs)
        car_index = event_content.carIndex

        try:
            driver = self.cars[car_index].get('driverName', f'Car {car_index}')
        except KeyError:
            driver = f'Unknown Car {car_index}'

        accident_msg = f"{accident_time} - Accident involving: {driver}"

        # Get the full unparsed raw UDP data
        raw_data = self.extract_unparsed_data(full_event)

        # Combine messages
        full_message = f"{accident_msg}\nFull Event Data:\n{raw_data}\n"

        # Log to console
        print(full_message)

        # Log to file
        if self.output_file:
            try:
                with open(self.output_file, 'a', encoding='utf-8') as f:
                    f.write(full_message + '\n')
            except Exception as e:
                print(f"Error writing to log file: {e}")

    def extract_unparsed_data(self, event):
        """
        Retrieve and format all available event information including metadata and content.
        This method builds a dictionary containing:
         - Event metadata (if available): timestamp, name, topic.
         - All attributes from the event's content.
        The result is then pretty-printed for readability.
        """
        full_info = {}

        # Include event-level metadata if available
        if hasattr(event, 'timestamp'):
            full_info['timestamp'] = event.timestamp
        if hasattr(event, 'name'):
            full_info['name'] = event.name
        if hasattr(event, 'topic'):
            full_info['topic'] = event.topic

        # Attempt to get all attributes from the event content.
        content = event.content
        try:
            # Try to use __dict__ if available
            content_dict = content.__dict__
        except AttributeError:
            # Fallback: iterate over attributes manually
            content_dict = {}
            for attr in dir(content):
                if not attr.startswith('_') and not callable(getattr(content, attr)):
                    content_dict[attr] = getattr(content, attr)

        full_info['content'] = content_dict

        # Use pprint to format the dictionary nicely
        return pprint.pformat(full_info, indent=2)

    def format_time(self, milliseconds):
        """Format milliseconds into HH:MM:SS"""
        if milliseconds is None:
            return "00:00:00"
        seconds = int(milliseconds // 1000)
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def run(self):
        """Main run loop"""
        print("\nACC Accident Monitor")
        print("===================")
        print("\nConnecting to ACC...")

        self.setup_output_file()
        self.setup_client()
        self.start_client()

        print("\nMonitoring for accidents...")
        print("Press Ctrl+C to stop monitoring\n")

        try:
            while self.running:
                if not self.client.isAlive:
                    print("\nLost connection to ACC. Attempting to reconnect...")
                    self.start_client()

        except KeyboardInterrupt:
            print("\nStopping accident monitoring...")
            self.running = False
            if self.client.isAlive:
                self.client.stop()
            print("Monitoring stopped.")


def main():
    monitor = AccidentMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
