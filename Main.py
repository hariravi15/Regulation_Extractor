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
        SampleText = " ".join([Doc.page_content for Doc in LangchainDocuments[:2]])[:1000]
        CheckPrompt = f"""You are a system analyst. Determine if the following content looks like a system or technical requirement document.

Text:\"\"\"{SampleText}\"\"\"
Respond with either "Yes" or "No" only.
"""
        CheckResponse = Client.chat.completions.create(model="gpt-3.5-turbo",messages=[{"role": "user", "content": CheckPrompt}])
        if "yes" in CheckResponse.choices[0].message.content.strip().lower():
            st.success("Document looks like a requirement document.")
            with st.spinner("Extracting system requirements..."):
                Embeddings = OpenAIEmbeddings()
                VectorStore = InMemoryVectorStore.from_documents(LangchainDocuments, Embeddings)
                SearchQuery = "type approval extension requirements"
                RetrievedDocs = VectorStore.similarity_search(SearchQuery, k=5)
                SystemRequirements = []

                for Index, RetrievedDoc in enumerate(RetrievedDocs, 1):
                    OriginalText = RetrievedDoc.page_content.strip().replace("\n", " ")
                    RequirementPrompt = f"""You are a systems engineer. Convert the following technical content into a clear system requirement using 'The system must...' format.

Content: "{OriginalText}"
Output:
"""
                    Response = Client.chat.completions.create(model="gpt-3.5-turbo",messages=[{"role": "user", "content": RequirementPrompt}])
                    FormattedRequirement = Response.choices[0].message.content.strip()
                    SystemRequirements.append({"Requirement No.": f"Requirement {st.session_state.RunId}.{Index}","Page": RetrievedDoc.metadata["page"],"System Requirement": FormattedRequirement})
       
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
            st.error("This doesn't appear to be a requirements document. Please upload another.")

        PdfDoc.close()
        os.remove(TempPath)
