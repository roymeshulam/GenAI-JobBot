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

```sh
git clone https://github.com/roymeshulam/GenAI-JobBot.git
cd GenAI-JobBot
```

Create a virtual environment:

```sh
python -m venv venv
```

Then,
- On Unix, use
  ```sh
  source venv/bin/activate
  ```
- On Windows, use
  ```sh
  venv\Scripts\activate
  ```

Install the required packages:

```sh
pip install -r requirements.txt
```

This project uses Python 3.12.6. Please ensure you have this version installed to avoid compatibility issues.

# Configuration

- Create a `.env` file based on the template `.env.template` and fill in the relevant details.
- Save an updated resume as `resume.docx` under the data folder.
- Create a `resume.yaml` file based on the template `resume.yaml.template` and fill in the relevant details (you may try to upload your resume together with the YAML template to have it auto-filled).
- Create a `config.yaml` based on the template provided and fill in the relevant details.
- Set up a PostgreSQL database and save the login details in the format of `postgresql://...` in the `.env` file.

Create the `jobs` table:

```sql
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

Create the `questions` table:

```sql
CREATE TABLE questions (
    id SERIAL PRIMARY KEY,
    type VARCHAR(50),
    question VARCHAR(4096),
    answer VARCHAR(4096)
);
```

# Usage

```sh
python main.py
```

The application will automatically log in to LinkedIn and start applying for jobs based on your configuration.

# License

This project is licensed under the MIT [License](License).

# Contributing

Contributions are welcome! Please read the [CONTRIBUTING.md](CONTRIBUTING.md) for details on the process for submitting pull requests.

# Contact

For any questions or feedback, please contact me at roy.meshulam@gmail.com.