class VisionProcessor:
    def __init__(self):
        self.cell_queue = []
        
    def process_cells(self, cell_data):
        """
        Loads all detected cell coordinates into a single task queue.
        Clears previous queues before processing new battery cells.
        """
        self.cell_queue.clear()
        
        for data in cell_data:
            self.cell_queue.append(data)
                
    def get_next_target(self):
        """Pops and returns the next target for the robot."""
        if self.cell_queue:
            return self.cell_queue.pop(0)
        return None
        
    def is_work_remaining(self):
        """Checks if there are still cells left to extract."""
        return len(self.cell_queue) > 0