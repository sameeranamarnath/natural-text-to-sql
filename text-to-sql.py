#text-to-sql using langchain, g4f
#Amar nov25 

import streamlit as st

from g4f import Provider, models
from langchain.llms.base import LLM

from langchain_g4f import G4FLLM
from langchain.llms import OpenAI
from langchain.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from langchain.agents import create_sql_agent
from langchain.agents.agent_types import AgentType
from langchain.agents.agent_toolkits import SQLDatabaseToolkit
import os
from dotenv import load_dotenv 








st.title('Run Sql queries on database using natural language via langchain & gpt3.5/4')
#llm2: LLM = G4FLLM(
#        model=models.gpt_35_turbo,
#        provider=Provider.Bing,
#    )
#print(llm2("hello stranger"))

load_dotenv()
def generate_response(openai_api_key,input_text,database_uri,use_free_version): 
     
     if not database_uri:
      existingConnector =  os.environ["omdb_url"]
      #sample format: postgresql+psycopg2://username:password@ep-floral-frog-97311990-pooler.ap-southeast-1.aws.neon.tech/omdb?sslmode=require&options=endpoint%3Dep%2Dfloral%2Dfrog%2D97311990%2Dpooler
      db = SQLDatabase.from_uri(existingConnector)
     else:
      db = SQLDatabase.from_uri(database_uri)
     if not use_free_version:
      llm = OpenAI( temperature=0, verbose=True, openai_api_key=openai_api_key,max_tokens=4096)
     else:
      llm: LLM = G4FLLM(
        model=models.gpt_35_turbo,
        provider=Provider.FreeGpt,
    )
     #toolkit = SQLDatabaseToolkit(db=db, llm=llm)
  
     try:
      db_chain = SQLDatabaseChain.from_llm(llm, db, verbose=True, return_intermediate_steps=True)
      response = db_chain(input_text)
      intermediateSteps=response["intermediate_steps"]
     #answer=response["result"]
      st.info(response["result"])
      #st.info(intermediateSteps)
     except Exception as e:
      st.info(e) 

     #   agent_executor = create_sql_agent(
     #           llm=llm,
     #           toolkit=toolkit,
     #           verbose=True,
     #           agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
     #                handle_parsing_errors=True
     #           )
     #      st.info(agent_executor.run(question))
     
     

with st.form('data_form'):
  question = st.text_area('Enter a question in natural language for the AI on the  omdb movies postgres database')
  database_uri = st.text_area("share a sqlachemy compatible uri for a remote sql based db if you want to use another dataset ")
  use_free_version = st.checkbox(" use free version with g4f and langchaing4f instead of openai, may be slow",disabled=True,value=True)
  openai_api_key =st.text_area('Please enter your OpenAI API Key if you wanna use the paid api,ensure you have credits')

  st.text("currently used database is omdb hosted on neon sql with the following format :postgresql+psycopg2://username:password@ep-floral-frog-97311990-pooler.ap-southeast-1.aws.neon.tech/omdb?sslmode=require&options=endpoint%3Dep%2Dfloral%2Dfrog%2D97311990%2Dpooler")

  st.text("another sample database to try  is:  sqlite:///imdb-movie.sqlite    which is stored locally")
  submitted = st.form_submit_button('Submit')
  #if not openai_api_key.startswith('sk-'):
  #st.warning('Please enter your OpenAI API key!', icon='âš ')
  if submitted:
   generate_response(openai_api_key,question,database_uri,use_free_version)
