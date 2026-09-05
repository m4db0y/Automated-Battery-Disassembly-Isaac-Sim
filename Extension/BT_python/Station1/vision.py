class VisionProcessor:
    def __init__(self):
        self.left_queue = []
        self.right_queue = []
        
    def process_screws(self, screw_data):
        """
        Splits data into left and right queues based on the Y-axis.
        Clears previous queues before processing new battery screws.
        """
        self.left_queue.clear()
        self.right_queue.clear()
        
        for data in screw_data:
            # Unpack the path and coordinate bundle
            path, coord = data
            y_value = coord[1]
            
            if y_value > 0:
                self.left_queue.append(data)
            else:
                self.right_queue.append(data)
                
    def get_next_target_left(self):
        """Pops and returns the next target for the left robot."""
        if self.left_queue:
            return self.left_queue.pop(0)
        return None

    def get_next_target_right(self):
        """Pops and returns the next target for the right robot."""
        if self.right_queue:
            return self.right_queue.pop(0)
        return None
        
    def is_work_remaining(self):
        """Checks if there are still screws left to assign in either queue."""
        return len(self.left_queue) > 0 or len(self.right_queue) > 0