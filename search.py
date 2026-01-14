from typing import List, Dict, Optional
from database import Database

def search_samples(db: Database, 
                   query: Optional[str] = None,
                   person: Optional[str] = None,
                   antibiotic: Optional[str] = None,
                   location: Optional[str] = None) -> List[Dict]:
    """
    Search samples using full-text search and/or filters.
    Combines both approaches if both query and filters are provided.
    """
    
    # If we have a text query, use full-text search
    if query:
        results = db.search_samples(query)
        
        # Apply additional filters if provided
        if person or antibiotic or location:
            filtered = []
            for result in results:
                matches = True
                
                if person and person.lower() not in (result.get('person') or '').lower():
                    matches = False
                
                if antibiotic and antibiotic.lower() not in (result.get('antibiotic') or '').lower():
                    matches = False
                
                if location and location.lower() not in (result.get('location') or '').lower():
                    matches = False
                
                if matches:
                    filtered.append(result)
            
            return filtered
        
        return results
    
    # If only filters, use filter method
    elif person or antibiotic or location:
        return db.filter_samples(person=person, antibiotic=antibiotic, location=location)
    
    # If nothing provided, return all
    else:
        return db.get_all_samples()
