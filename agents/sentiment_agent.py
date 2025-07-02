from crewai import Agent
from langchain_anthropic import ChatAnthropic


sentiment_llm = ChatAnthropic(model="claude-3-sonnet-20240229")

SentimentMonitorAgent = Agent(
    role="Sentiment Monitor",
    goal="Determine the public sentiment from a given news article",
    backstory="You're responsible for understanding how the public and media feel about key companies like Tesla or Palantir.",
    verbose=True,
    allow_delegation=False,
    llm=sentiment_llm,
)
