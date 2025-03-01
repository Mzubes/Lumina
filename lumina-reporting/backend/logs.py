import logging

# Configure logging
logging.basicConfig(filename='security.log', level=logging.INFO, format='%(asctime)s - %(message)s')

def log_action(message):
    logging.info(message)
