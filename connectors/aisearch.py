# write class to setup FAISS vector store and use it to search for similar documents
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenAIEmbeddings
import os

class AISearch:
    def __init__(self, index_path: str):
        self.index_path = index_path
        self.embeddings = OpenAIEmbeddings()
        self.vector_store = None

    def setup_vector_store(self, documents: list):
        # Create a FAISS vector store from the documents
        self.vector_store = FAISS.from_texts(documents, self.embeddings)
        # Save the vector store to disk
        self.vector_store.save_local(self.index_path)

    def load_vector_store(self):
        # Load the vector store from disk
        if os.path.exists(self.index_path):
            self.vector_store = FAISS.load_local(
                self.index_path,
                self.embeddings,
                allow_dangerous_deserialization=True,
            )
        else:
            raise FileNotFoundError(f"Vector store not found at {self.index_path}")

    def search(self, query: str, k: int = 3):
        if not self.vector_store:
            raise ValueError("Vector store is not loaded. Please load it before searching.")
        # Search for similar documents
        results = self.vector_store.similarity_search(query, k=k)
        return results
    
if __name__ == "__main__":
    # Example usage
    documents = azerbaijan_packages = {
    """Azerbaijan 6 nights 7 days itinerary with Gabala stay. Includes Baku city tour, Gabala tour, Shamakhi tour, Absheron Peninsula tour and shopping tour.
    Day 1 itinerary: Arrival in Baku. Panoramic tour including Flame Towers, Highland Park, Seaside Park. Hotel check-in and overnight stay in Baku.
    Day 2 itinerary: Baku city tour visiting Heydar Aliyev Center, Maiden Tower in Old City, Baku Boulevard, Little Venice, Carpet Museum, Philharmonic Fountain, Shirvanshahs Palace, Flame Towers.
    Day 3 itinerary: Travel from Baku to Gabala with Shamakhi city tour stops including Juma Mosque, Alpaca Farm and Diri Baba Mausoleum.
    Day 4 itinerary: Gabala city tour including Nohur Lake, 7 Beauties Waterfall, Shooting Club, Tufandag Mountain Resort cable car ride and riverside walk.
    Day 5 itinerary: Return from Gabala to Baku and enjoy a shopping tour in major Baku shopping centers and entertainment areas.
    Day 6 itinerary: Absheron Peninsula and Gobustan tour including Yanar Dag burning mountain, Fire Temple, Rock Museum and Mud Volcano.
    Day 7 itinerary: Airport transfer from Baku hotel to airport.
    Package inclusions: Airport transfers, hotel accommodation, buffet breakfast, taxes and private sedan vehicle for tours.
    Package exclusions: Lunch, dinner, Azerbaijan e-visa cost and entry tickets to attractions.
    Hotel option 1: Volga Hotel Baku 3 star for 4 nights and Lakeside Hotel Gabala 3 star for 2 nights. Total package price 2335 AED.
    Hotel option 2: Port Rivoli Hotel Baku 3 star for 4 nights and Nohur Lake Hotel Gabala 3 star for 2 nights. Total package price 2668 AED.
    Hotel option 3: Iris Hotel Baku 4 star for 4 nights and Hill Chalet Hotel Gabala 4 star for 2 nights. Total package price 3038 AED.""",

    """Azerbaijan 5 nights 6 days itinerary with 1 night stay in Gabala and remaining nights in Baku.
    Day 1: Arrival in Baku with panoramic tour visiting Flame Towers, Highland Park and Seaside Park.
    Day 2: Baku city tour visiting Heydar Aliyev Center, Maiden Tower, Baku Boulevard, Little Venice, Carpet Museum and Shirvanshahs Palace.
    Day 3: Transfer to Gabala and Gabala sightseeing including Nohur Lake, 7 Beauties Waterfall, Shooting Club and Tufandag Mountain cable car.
    Day 4: Return to Baku with Shamakhi city tour stops including Juma Mosque, Alpaca Farm and Diri Baba Mausoleum.
    Day 5: Absheron Peninsula and Gobustan tour visiting Yanar Dag burning mountain, Fire Temple, Rock Museum and Mud Volcano.
    Day 6: Airport transfer in Baku.
    Hotel option 1: Volga Hotel Baku 3 star for 4 nights and Lakeside Hotel Gabala 3 star for 1 night. Total price 2002 AED.
    Hotel option 2: Port Rivoli Hotel Baku 3 star for 4 nights and Nohur Lake Hotel Gabala 3 star for 1 night. Total price 2298 AED.
    Hotel option 3: Iris Hotel Baku 4 star for 4 nights and Hill Chalet Hotel Gabala 4 star for 1 night. Total price 2594 AED.""",

    """Azerbaijan 3 nights 4 days tour package based in Baku with city tour and Quba Shahdag excursion.
    Day 1: Arrival in Baku and panoramic tour including Flame Towers, Highland Park and Seaside Park.
    Day 2: Baku city tour and Absheron Peninsula tour visiting Heydar Aliyev Center, Maiden Tower, Baku Boulevard, Carpet Museum, Shirvanshahs Palace, Yanar Dag and Fire Temple.
    Day 3: Quba and Shahdag day trip including Qechresh Forest, Qudyal River, Chanlibel Lake and Shahdag Resort.
    Day 4: Airport transfer from hotel to airport.
    Hotel option 1: Volga Hotel Baku 3 star for 3 nights. Price 1484 AED.
    Hotel option 2: Port Rivoli Hotel Baku 3 star for 3 nights. Price 1632 AED.
    Hotel option 3: Iris Hotel Baku 4 star for 3 nights. Price 1817 AED.""",

    """Azerbaijan visa rule: UAE residents with at least 6 months valid UAE residence permit can obtain visa on arrival or apply for an e-visa.
    Azerbaijan tourist visa allows a stay of up to 30 days and passport validity should be at least 6 months.
    Visa on arrival cost for Azerbaijan is approximately 40 USD at the airport.
    Azerbaijan e-visa applied online costs around 130 AED.
    Indian passport holders can apply for Azerbaijan e-visa or obtain visa on arrival if eligible.
    Pakistan, Bangladesh, Nepal, Sri Lanka and Philippines citizens normally apply for Azerbaijan e-visa online before travel.
    GCC nationals from Saudi Arabia, Kuwait, Bahrain, Qatar and Oman can usually obtain visa on arrival.
    Citizens of Syria, Iraq and Afghanistan normally require embassy visa for Azerbaijan.""",

    "Halal food is widely available in Azerbaijan because the country has a Muslim majority population.",

    "Flight duration from UAE to Baku is approximately 3 hours.",

    "Travelers visiting Azerbaijan are advised to carry at least 250 USD or equivalent amount in Azerbaijani Manat for personal expenses during the trip.",

    """Travelers should ideally buy a SIM card at the airport upon arrival in Azerbaijan. Airport kiosks usually offer cheaper and more reliable tourist SIM packages.
    SIM cards purchased inside the city in Azerbaijan can sometimes be significantly more expensive. Some shops may charge up to 95 USD for tourist SIM packages.""",

    """It is not recommended to rely completely on international debit or credit cards while traveling in Azerbaijan. Some smaller shops and local businesses may prefer cash payments.
    International bank cards may have daily spending limits and additional transaction or currency conversion fees when used in Azerbaijan.
    Travelers are advised to carry sufficient cash in USD or Azerbaijani Manat for daily expenses when visiting Azerbaijan.""",

    """Child pricing policy: Children below 5 years can join the tour free of charge, but flight tickets are chargeable.
    For children below 5 years, visa charges and travel insurance costs are still applicable even though the tour itself is free."""
    }
    index_path = "knowledgebase"
    ai_search = AISearch(index_path)
    # ai_search.setup_vector_store(documents)
    ai_search.load_vector_store()
    query = "what all the package options available for Azerbaijan tour?"
    results = ai_search.search(query)
    print(results)