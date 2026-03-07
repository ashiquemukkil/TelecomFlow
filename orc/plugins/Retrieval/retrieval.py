from semantic_kernel.functions import kernel_function
from connectors.aisearch import AISearch
import sys
if sys.version_info >= (3, 9):
    from typing import Annotated
else:
    from typing_extensions import Annotated

    
class Retrieval:
    def __init__(self):
        index_path = "knowledgebase"
        ai_search = AISearch(index_path)
        ai_search.load_vector_store()
        self.ai_search = ai_search

    @kernel_function(
        description="Search a knowledge base for sources to ground and give context to answer a user question. Return sources.",
        name="VectorIndexRetrieval",
    )
    async def VectorIndexRetrieval(
        self,
        input: Annotated[str, "The user question"]
    ) -> Annotated[str, "the output is a string with the search results"]:
        search_results = []
        search_query = input
       
        try:
            results = self.ai_search.search(search_query, k=3)
            search_results = [result.page_content for result in results]
    
        except Exception:
            pass
        sources = ' '.join(search_results)
        return sources
