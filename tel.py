import openai
import json
import time
from datetime import datetime
from telegram.ext import Application, JobQueue
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
openai.api_key = os.getenv('OPENAI_API_KEY')

if not all([TOKEN, CHAT_ID, openai.api_key]):
    raise ValueError("One or more environment variables are missing. Please check your .env file.")

last_question = None

def generate_quiz_data():
    """
    Generate a challenging Ruby or Ruby on Rails-related quiz question with an explanation.
    Implements a retry mechanism with exponential backoff to handle empty or invalid API responses.
    """
    prompt = """
    You are an expert in Ruby programming and the Ruby on Rails framework.

    Generate a challenging multiple-choice quiz question for advanced Ruby developers.

    Instructions:
    - The question should focus on advanced Ruby or Rails topics.
    - Provide 4 distinct options, each not exceeding 100 characters.
    - Specify the correct answer by its index (0-based).
    - Include a brief explanation (up to 200 characters) of the correct answer.
    - Vary topics across different areas of Ruby and Rails, avoiding repetition of subjects like Lambda and Proc.

    Output a single JSON object (no extra text) with:
    - "question": The Ruby/Rails question.
    - "options": A list of 4 possible answers.
    - "correct_option_id": Index (0-based) of the correct answer.
    - "explanation": A brief explanation of the correct answer.

    Example:
    {
      "question": "What is the purpose of the `before_action` callback in Rails?",
      "options": ["Execute code before action", "Handle routing", "Manage background jobs", "Define middleware"],
      "correct_option_id": 0,
      "explanation": "`before_action` runs specified methods before controller actions, often for setup tasks."
    }
    """

    # Try up to 3 times before falling back
    for attempt in range(3):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=250,
                temperature=0.8
            )
            # Check if response and content are valid
            if not response or not response.choices or not response.choices[0].message:
                raise ValueError("Empty response from API")
            gpt_content = response.choices[0].message["content"].strip()
            if not gpt_content:
                raise ValueError("Empty content received from API")

            # Log raw content for debugging if needed
            # print("Raw GPT response:", gpt_content)

            quiz_data = json.loads(gpt_content)

            # Prevent repeated questions
            global last_question
            if quiz_data.get('question') == last_question:
                raise ValueError("Repeated question detected, regenerating...")

            last_question = quiz_data.get('question')
            return quiz_data

        except Exception as e:
            print(f"Attempt {attempt+1}: Error generating or parsing quiz data: {str(e)}")
            time.sleep(2 ** attempt)  # Exponential backoff

    # Fallback quiz question if all attempts fail
    return {
        "question": "What is the difference between 'include' and 'extend' in Ruby?",
        "options": [
            "Include adds methods as instance methods",
            "Extend adds methods as class methods",
            "Both add instance methods",
            "Neither adds methods"
        ],
        "correct_option_id": 0,
        "explanation": "'include' mixes in module methods as instance methods; 'extend' does so for class methods."
    }

async def send_quiz(context):
    """
    Sends a quiz question (poll) in a Telegram group with multiple choices,
    using the 'quiz' type to show the correct answer and an explanation after the user answers.
    """
    quiz_data = generate_quiz_data()
    question = quiz_data.get("question", "Sample question")
    options = quiz_data.get("options", ["Option 1", "Option 2", "Option 3", "Option 4"])
    correct_id = quiz_data.get("correct_option_id", 0)
    explanation = quiz_data.get("explanation", "No explanation provided.")

    try:
        await context.bot.send_poll(
            chat_id=CHAT_ID,
            question=question,
            options=options,
            type="quiz",              # Enable quiz mode
            correct_option_id=correct_id,
            explanation=explanation,  # Provide explanation after answer
            is_anonymous=False
        )
        print(f"✅ Quiz sent at {datetime.now()}: {question}")
    except Exception as e:
        print(f"❌ Failed to send quiz: {str(e)}")

def main():
    application = Application.builder().token(TOKEN).build()

    # Optional test message to ensure bot is running
    async def send_test_message():
        await application.bot.send_message(chat_id=CHAT_ID, text="Test Ruby quiz from bot")
        print("✅ Test message sent.")

    job_queue = application.job_queue
    job_queue.run_repeating(send_quiz, interval=30, first=10)  # Runs every 7200 seconds, starting after 10 seconds

    print("🚀 Job queue scheduled...")
    print("📡 Starting bot polling...")
    application.run_polling()
    print("🛑 Bot shutdown complete.")

if __name__ == "__main__":
    main()
