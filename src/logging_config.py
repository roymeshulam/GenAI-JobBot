import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("log.txt", mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ],
    force=True  # This will reset the root logger's handlers and apply the new configuration
)

logger = logging.getLogger(__name__)
