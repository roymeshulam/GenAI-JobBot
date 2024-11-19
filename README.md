# GenAI-JobBot
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
```
Then,
- On Unix, use
```
source venv/bin/activate
```
- On Windows, use
```
venv\Scripts\activate
```
Install the required packages:
```
pip install -r requierments.txt
```

# Configuration
- Create a .env file based on the template .env.template and fill in the relevant details.

- Save an updated resumse as resume.docx under the data folder.

- Create a resume.yaml file based on the template resume.yaml.template and fill in the relevant details (you may try to upload your resume together with the yaml template to have it auto filled.).

- Create a config.yaml based on the template provided and fill in the relevant details.

- Setup a postgresql database and save the login details in the format of postgresql://... in the .env file

- Create the jobs table:
```
CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    company VARCHAR(255),
    title VARCHAR(255),
    link TEXT,
    recruiter TEXT,
    location VARCHAR(255),
    applied BOOLEAN,
    connected BOOLEAN
);
```

- Create the questions table:
```
CREATE TABLE questions (
    id SERIAL PRIMARY KEY,
    type VARCHAR(50),
    question VARCHAR(4096),
    answer VARCHAR(4096)
);
```

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
