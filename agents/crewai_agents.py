from crewai import Agent, Task
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv
import os

load_dotenv()

llm = ChatAnthropic(
    temperature=0.3,
    model="claude-3-sonnet-20240229"
)

summarizer_agent = Agent(
    role="Strategic News Analyst",
    goal="Summarize relevant news articles into key business and geopolitical insights",
    backstory="You work for a major defense and strategy firm...",
    verbose=True,
    allow_delegation=False,
    llm=llm
)

def create_summarize_task(input_articles: str):
    return Task(
        description="Summarize the following news articles into bullet points:\n" + input_articles,
        expected_output="A short, clear summary with actionable insights and flagged risks",
        agent=summarizer_agent
    )
