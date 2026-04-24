import streamlit as st
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from openai import OpenAI
import fitz 
import pandas as pd
import os
import uuid

st.title("System Requirement Extractor")

Client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "RunId" not in st.session_state:
    st.session_state.RunId = 1

UploadedFile = st.file_uploader("Upload a PDF Requirement Document", type="pdf")

if UploadedFile is not None:
    with st.spinner("Reading and analyzing the document..."):
        TempPath = f"temp_{uuid.uuid4()}.pdf"
        with open(TempPath, "wb") as File:
            File.write(UploadedFile.read())

        PdfDoc = fitz.open(TempPath)
        Pages = [{"Page": PageNumber + 1, "Content": Page.get_text("text")} for PageNumber, Page in enumerate(PdfDoc)]
        LangchainDocuments = [Document(page_content=Page["Content"], metadata={"page": Page["Page"]}) for Page in Pages]
        
        SampleText = " ".join([Doc.page_content for Doc in LangchainDocuments[:5]])[:4000]
        
        CheckPrompt = f"""You are a technical and regulatory analyst. Determine if the following text contains technical specifications, regulatory standards, or system requirements.
Text:\"\"\"{SampleText}\"\"\"
Respond with either "Yes" or "No" only."""

        CheckResponse = Client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": CheckPrompt}])
        
        if "yes" in CheckResponse.choices[0].message.content.strip().lower():
            st.success("Document verified. Extracting requirements...")
            with st.spinner("Processing..."):
                Embeddings = OpenAIEmbeddings()
                VectorStore = InMemoryVectorStore.from_documents(LangchainDocuments, Embeddings)
                
                TitleContext = LangchainDocuments[0].page_content[:500]
                TopicGen = Client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": f"Provide a 5-word search query to find the primary technical requirements in this document: {TitleContext}"}]
                )
                SearchQuery = TopicGen.choices[0].message.content.strip()
                
                RetrievedDocs = VectorStore.similarity_search(SearchQuery, k=10)
                SystemRequirements = []

                for Index, RetrievedDoc in enumerate(RetrievedDocs, 1):
                    OriginalText = RetrievedDoc.page_content.strip().replace("\n", " ")
                    RequirementPrompt = f"""You are a systems engineer. Convert the following technical or regulatory content into a clear system requirement using 'The system must...' format.
Content: "{OriginalText}"
Output:"""
                    Response = Client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": RequirementPrompt}])
                    FormattedRequirement = Response.choices[0].message.content.strip()
                    SystemRequirements.append({
                        "Requirement No.": f"Req {st.session_state.RunId}.{Index}",
                        "Page": RetrievedDoc.metadata["page"],
                        "System Requirement": FormattedRequirement
                    })
        
                DataFrame = pd.DataFrame(SystemRequirements)
                OutputFile = f"system_requirements_{st.session_state.RunId}.xlsx"
                DataFrame.to_excel(OutputFile, index=False)
              
                st.session_state.RunId += 1
             
                with open(OutputFile, "rb") as File:
                    st.download_button(
                        label="Download Requirements Excel",
                        data=File,
                        file_name=OutputFile,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                os.remove(OutputFile)
        else:
            st.error("This document does not appear to contain technical or system requirements.")

        PdfDoc.close()
        os.remove(TempPath)
