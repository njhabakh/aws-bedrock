import json
import os
import sys
import boto3
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

## We will be using Titan Embeddings Model To generate Embedding

from langchain_community.embeddings import BedrockEmbeddings
from langchain.llms.bedrock import Bedrock
from langchain_community.chat_models.bedrock import BedrockChat

## Data Ingestion

import numpy as np
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFDirectoryLoader

# Vector Embedding And Vector Store
# from langchain_community.vectorstores import FAISS
from langchain.vectorstores import FAISS

## LLm Models
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from pypdf import PdfReader
from langchain.schema import Document

## Bedrock Clients
bedrock=boto3.client(service_name="bedrock-runtime")
bedrock_embeddings=BedrockEmbeddings(model_id="amazon.titan-embed-text-v1",client=bedrock)



def extract_pdf(filename):
    '''
    Extract all text of the PDF Data into one string
    args : 
        filname - name of the .pdf file
    returns:
        all_text - string output of all the text
    '''
    reader = PdfReader(filename)
    all_text = " "
    for i in range(0,len(reader.pages)):
        page = reader.pages[i]
        all_text = all_text + page.extract_text()
    return all_text


def extract_pdf_docs(filename):
    '''
    Extract PDF Data as Docs per page
    args : 
        filname - name of the .pdf file
    returns:
        docs - Document output per page of the pdf file
    '''
    reader = PdfReader(filename)
    docs = []
    for i in range(0,len(reader.pages)):
        page = reader.pages[i]
        docs.append(Document(page_content=page.extract_text()))
    return docs

## Data ingestion
def data_ingestion(dir):
    '''
    Extract PDF files from a directory and returns chunked docs
    args : 
        filname - name of the .pdf file
    returns:
        docs - Document output per chunk of the pdf files
    '''
    loader=PyPDFDirectoryLoader(dir)
    documents=loader.load()

    # - in our testing Character split works better with this PDF data set
    text_splitter=RecursiveCharacterTextSplitter(chunk_size=10000,
                                                 chunk_overlap=1000)
    
    docs=text_splitter.split_documents(documents)
    return docs

## Vector Embedding and vector store
def get_vector_store(docs, inp):
    '''
    Extract PDF files from a directory and returns chunked docs
    args : 
        docs - Document input of the pdf file or files
        inp - directory location based on guideline
    returns:
    '''
    vectorstore_faiss=FAISS.from_documents(
        docs,
        bedrock_embeddings
    )
    vectorstore_faiss.save_local(f"faiss_index_{inp}")

def get_claude_llm():
    ##create the Anthropic Model
    llm=BedrockChat(model_id="anthropic.claude-3-sonnet-20240229-v1:0",client=bedrock,
                model_kwargs={'max_tokens':1000})
    
    return llm

def get_llama2_llm():
    ##create the Anthropic Model
    llm=Bedrock(model_id="meta.llama2-70b-chat-v1",client=bedrock,
                model_kwargs={'max_gen_len':200})
    
    return llm


prompt_template_chat = """

Human: Use the following pieces of context to provide a 
concise answer to the question at the end but usse atleast summarize with 
250 words with detailed explantions. If you don't know the answer, 
just say that you don't know, don't try to make up an answer.
<context>
{context}
</context

Question: {question}

Assistant:"""

# Completeness check
# General Compliance
# Key Things

prompt_template_compliance = """
Imagine you are a compliance officer for a bank checking if policies and guidelines are being met.
Check the sections of the following document on whether the policies are being met.
<question>
{question}
</question

The following are the poilicies to be checked against:
<context>
{context}
</context

Provide the summary of the non-compliant sections 
and a high level yes, no or partially compliant
in tabular form with the summary of the non-compliant section in one column, 
yes or no in the other column and 
the high level reason of non compliance or partial compliance in less than 5 words. 
Also provide the detailed summary under the table with the non compliant or partially compliant 
sections with quoted reference and suggested change. 
Please refer only to the document. 
Please be formal in your response. 
Please avoid any biases.
Assistant:"""

prompt_template_compliance_upd = """
Imagine you are a compliance officer for a bank checking if policies and guidelines are being met.
Check the sections of the following question on whether the policies and guidelines are being met.
<question>
{question}
</question

These are the sections of the above document to be checked with the below policies and guidelines.
<sections>
{section}
</sections

The following are the policies and guidelines to be checked against:
<context>
{context}
</context

Provide a high level response table of the question with a single word - Yes, No or Partially Compliant for each section of the question as a table.
The first column of the table is the section, second column is the check for compliance with a Yes, No or Partially Compliant.
Provide a detailed summary under the high level response table for the non compliant or partially compliant 
sections of the context with quoted reference from the context above and suggested change. 
Please refer only to the document. 
Please be formal in your response. 
Please avoid any biases.
Assistant:"""

PROMPT1 = PromptTemplate(
    template=prompt_template_compliance, input_variables=["context", "question"]
)


sections_txt = '''
1. Introduction
2. Scope
3. Governance and Strategy
4. Risk Management Framework
5. Information Security
6. ICT Operations Management
7. Business Continuity Management
8. Compliance and Reporting
9. Training and Awareness
'''

PROMPT2 = PromptTemplate(
    template=prompt_template_compliance_upd.replace('{section}',sections_txt), input_variables=["context", "question"]
)

def get_response_llm(llm,vectorstore_faiss,query, PROMPT):
    qa = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=vectorstore_faiss.as_retriever(
        search_type="similarity", search_kwargs={"k": 10}
    ),
    return_source_documents=True,
    chain_type_kwargs={"prompt": PROMPT}
)
    answer=qa({"query":query})
    return answer['result']


def main():
    st.set_page_config("Team LLM")

    uploaded_file = st.file_uploader('Choose your .pdf file', type="pdf")
    tab1, tab2, tab3 = st.tabs(["Compi-Ease", "Compliance-Bot", "Regu-sinc"])
    with tab1:
        # user_question = st.text_input("Ask a Question from the PDF Files")        
        if uploaded_file is not None:
            user_question = extract_pdf(uploaded_file)

        with st.sidebar:
            st.title("Update Or Create Vector Store:")
            
            if st.button("Vectors Update Guidelines"):
                with st.spinner("Processing..."):
                    docs = data_ingestion('guidelines')
                    get_vector_store(docs, 'guidelines')
                    st.success("Done")

        if st.button("EBA"):
            with st.spinner("Processing..."):
                faiss_index = FAISS.load_local("faiss_index_guidelines", bedrock_embeddings, allow_dangerous_deserialization=True)
                llm=get_claude_llm()
                
                st.write(get_response_llm(llm,faiss_index,user_question, PROMPT2))
                st.success("Done")

        if st.button("FINRA"):
            with st.spinner("Processing..."):
                faiss_index = FAISS.load_local("faiss_index_guidelines", bedrock_embeddings, allow_dangerous_deserialization=True)
                llm=get_claude_llm()
                
                st.write(get_response_llm(llm,faiss_index,user_question, PROMPT2))
                st.success("Done")

    with tab2:
        st.header("Compliance-Bot")


    with tab3:
        st.header("Regu-sinc")

    


if __name__ == "__main__":
    main()














