# ﻿GenAI-JobBot
Harnessing the power of Generative AI to automate job applications on LinkedIn.

# Description
GenAI-JobBot is a Python application designed to automate the job application process on LinkedIn. Using Generative AI, it fills in the necessary details and applies for positions seamlessly.

# Features
- Automates job applications on LinkedIn
- Uses Generative AI to fill in application questions
- Customizable for different job search criteria

# Setup
Clone the repository:
```
git clone https://github.com/yourusername/GenAI-JobBot.git
cd GenAI-JobBot
```
Create a virtual environment:
```
python -m venv venv
source venv/bin/activate
```
On Windows, use
```
venv\Scripts\activate
```
Install the required packages:
```
python .\update_packages.py
```

# Configuration
Create a .env file based on the template .env.template and fill in the relevant details:
```
LANGTRACE_API_KEY=LANGTRACE_API_KEY
LINKEDIN_EMAIL=LINKEDIN_EMAIL
LINKEDIN_PASSWORD=LINKEDIN_PASSWORD
LLM_API_KEY=LLM_API_KEY
LLM_MODEL_NAME=gpt-4o-mini
MODE=apply/reapply/reconnect/apply-langtrace/reapply-langtrace/reconnect-langtrace
DATABASE_URL=URL
```
Create a config.yaml based on the template provided:
```
---
experience_level:
  internship: false
  entry: false
  associate: false
  mid-senior level: true
  director: true
  executive: true
job_types:
  full-time: true
  contract: false
  part-time: false
  temporary: false
  internship: false
  other: false
  volunteer: false
date:
  all time: false
  month: false
  week: false
  24 hours: true
positions:
  - Artificial Intelligence
  - Data Scientist
  - Quantitative
  - Generative AI
locations:
  - United States
  - New Zealand
companies_blacklist:
  - Crossover
  - Jobot
```
Create 
# Usage
```
python main.py
```
The application will automatically log in to LinkedIn and start applying for jobs based on your configuration.

License
This project is licensed under the MIT License.

Contributing
Contributions are welcome! Please read the CONTRIBUTING.md for details on the process for submitting pull requests.

Contact
For any questions or feedback, please contact me at roy.meshulam@gmail.com
