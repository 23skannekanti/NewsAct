from agents.intel_gather_agent import gather_news
from agents.crewai_agents import create_summarize_task, summarizer_agent
from agents.sentiment_agent import SentimentMonitorAgent
from crewai import Crew, Task
from agents.mcp_agent import save_output

from email.mime.text import MIMEText
from email.utils import formatdate
import smtplib
import os
import re

def check_alert_condition(sentiment_score, summary_text):
    keywords = ["lawsuit", "bankruptcy", "resign", "crash", "investigation", "fraud"]
    return sentiment_score <= -0.5 or any(word in summary_text.lower() for word in keywords)

def send_email_alert(company, summary, sentiment):
    body = f""" Important News Alert for {company} 

Summary of Articles:
{summary}

Sentiment Score: {sentiment}

Timestamp: {formatdate(localtime=True)}

This alert was generated automatically by your Agentic AI monitoring system.
"""
    msg = MIMEText(body)
    msg["Subject"] = f"[ALERT] {company} News Triggered Agentic Alert"
    msg["From"] = os.getenv("EMAIL_SENDER")
    msg["To"] = os.getenv("EMAIL_RECIPIENT")

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(os.getenv("EMAIL_SENDER"), os.getenv("EMAIL_PASSWORD"))
        server.sendmail(msg["From"], [msg["To"]], msg.as_string())

if __name__ == "__main__":
    company = "Tesla"

    # Step 1: Gather articles
    articles = gather_news(company, num_articles=3)
    article_text = "\n\n".join(articles)

    # Step 2: Create tasks
    summarize_task = create_summarize_task(article_text)
    summarize_task.name = "summarize_task"

    sentiment_task = Task(
        description=f"Rate the sentiment of these news articles about {company} as Positive, Neutral, or Negative. Provide a score between -1 (very negative) to +1 (very positive). Justify briefly.",
        expected_output="A sentiment classification (Positive/Neutral/Negative) with score and 2-sentence reasoning.",
        agent=SentimentMonitorAgent,
    )
    sentiment_task.name = "sentiment_task"

    # Step 3: Run the crew
    crew = Crew(
        agents=[summarizer_agent, SentimentMonitorAgent],
        tasks=[summarize_task, sentiment_task],
        verbose=True
    )

    results = crew.kickoff()

    # Step 4: Display and save results
    print("\n=== FINAL OUTPUT ===\n")
    results_dict = results.to_dict()

    summary_text = ""
    sentiment_score = 0.0

    for task_name, output in results_dict.items():
        print(f"\n=== {task_name.upper()} ===\n")
        print(output)

        label = "summary" if "summarize" in task_name.lower() else "sentiment"
        save_output(company, label, output)

        if label == "summary":
            summary_text = output
        elif label == "sentiment":
            match = re.search(r'\(([-+]?[0-9]*\.?[0-9]+)\)', output)
            if match:
                sentiment_score = float(match.group(1))

    # Step 5: Check and send alert
    if check_alert_condition(sentiment_score, summary_text):
        send_email_alert(company, summary_text, sentiment_score)
        print("Email alert sent.")
    else:
        print("No alert triggered. News is not critical.")
