import streamlit as st
import requests
from datetime import datetime, timedelta
import os

# TfL API Configuration
TFL_APP_KEY = os.environ.get("TFL_APP_KEY", "your_app_key_here")
TFL_BASE_URL = "https://api.tfl.gov.uk"

st.set_page_config(page_title="TfL Journey Planner", page_icon="🚇", layout="wide")

# Custom CSS for better autocomplete display
st.markdown("""
<style>
    .suggestion-box {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
        cursor: pointer;
    }
    .suggestion-box:hover {
        background-color: #e0e2e6;
    }
</style>
""", unsafe_allow_html=True)

def search_locations(query):
    """Search for locations using TfL API"""
    if not query or len(query) < 3:
        return []
    
    try:
        url = f"{TFL_BASE_URL}/Place/Search"
        params = {
            "query": query,
            "app_key": TFL_APP_KEY,
            "maxResults": 10
        }
        
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        results = response.json()
        
        suggestions = []
        for place in results:
            name = place.get('name', '')
            place_type = place.get('placeType', '')
            address = place.get('address', '')
            lat = place.get('lat')
            lon = place.get('lon')
            
            suggestions.append({
                'display': f"{name} ({place_type})" if place_type else name,
                'name': name,
                'type': place_type,
                'lat': lat,
                'lon': lon,
                'id': place.get('id', ''),
                'full_address': address
            })
        
        return suggestions
    except Exception as e:
        st.error(f"Error searching locations: {str(e)}")
        return []

def search_stoppoints(query):
    """Search specifically for transport stops (stations, bus stops)"""
    if not query or len(query) < 2:
        return []
    
    try:
        url = f"{TFL_BASE_URL}/StopPoint/Search"
        params = {
            "query": query,
            "app_key": TFL_APP_KEY,
            "maxResults": 10
        }
        
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        suggestions = []
        if 'matches' in data:
            for match in data['matches']:
                name = match.get('name', '')
                modes = ', '.join(match.get('modes', []))
                lat = match.get('lat')
                lon = match.get('lon')
                
                suggestions.append({
                    'display': f"{name} [{modes}]",
                    'name': name,
                    'type': 'Stop',
                    'lat': lat,
                    'lon': lon,
                    'id': match.get('id', ''),
                    'modes': modes
                })
        
        return suggestions
    except Exception as e:
        return []

st.title("🚇 Transport for London Journey Planner")
st.markdown("Plan your journey across London using real-time TfL data")

# Initialize session state for selected locations
if 'origin_selected' not in st.session_state:
    st.session_state.origin_selected = None
if 'destination_selected' not in st.session_state:
    st.session_state.destination_selected = None
if 'origin_query' not in st.session_state:
    st.session_state.origin_query = ""
if 'destination_query' not in st.session_state:
    st.session_state.destination_query = ""

# Sidebar for inputs
with st.sidebar:
    st.header("Journey Details")
    
    # Origin input with autocomplete
    st.subheader("📍 From")
    origin_input = st.text_input(
        "Origin:",
        value=st.session_state.origin_query,
        placeholder="e.g., King's Cross, SW1A 1AA, or London Eye",
        key="origin_input"
    )
    
    # Show suggestions for origin
    if origin_input and len(origin_input) >= 2:
        if origin_input != st.session_state.origin_query or st.session_state.origin_selected is None:
            st.session_state.origin_query = origin_input
            
            with st.spinner("Searching..."):
                place_suggestions = search_locations(origin_input)
                stop_suggestions = search_stoppoints(origin_input)
                
                all_suggestions = place_suggestions + stop_suggestions
                seen = set()
                unique_suggestions = []
                for s in all_suggestions:
                    if s['name'] not in seen:
                        seen.add(s['name'])
                        unique_suggestions.append(s)
                
                if unique_suggestions:
                    st.markdown("**Suggestions:**")
                    for idx, suggestion in enumerate(unique_suggestions[:8]):
                        if st.button(
                            f"📍 {suggestion['display'][:60]}",
                            key=f"origin_sugg_{idx}",
                            use_container_width=True
                        ):
                            st.session_state.origin_selected = suggestion
                            st.session_state.origin_query = suggestion['name']
                            st.rerun()
    
    # Show selected origin
    if st.session_state.origin_selected:
        st.success(f"✓ {st.session_state.origin_selected['name']}")
    
    st.markdown("---")
    
    # Destination input with autocomplete
    st.subheader("📍 To")
    destination_input = st.text_input(
        "Destination:",
        value=st.session_state.destination_query,
        placeholder="e.g., Liverpool Street, E1 6AN, or Tower Bridge",
        key="destination_input"
    )
    
    # Show suggestions for destination
    if destination_input and len(destination_input) >= 2:
        if destination_input != st.session_state.destination_query or st.session_state.destination_selected is None:
            st.session_state.destination_query = destination_input
            
            with st.spinner("Searching..."):
                place_suggestions = search_locations(destination_input)
                stop_suggestions = search_stoppoints(destination_input)
                
                all_suggestions = place_suggestions + stop_suggestions
                seen = set()
                unique_suggestions = []
                for s in all_suggestions:
                    if s['name'] not in seen:
                        seen.add(s['name'])
                        unique_suggestions.append(s)
                
                if unique_suggestions:
                    st.markdown("**Suggestions:**")
                    for idx, suggestion in enumerate(unique_suggestions[:8]):
                        if st.button(
                            f"📍 {suggestion['display'][:60]}",
                            key=f"dest_sugg_{idx}",
                            use_container_width=True
                        ):
                            st.session_state.destination_selected = suggestion
                            st.session_state.destination_query = suggestion['name']
                            st.rerun()
    
    # Show selected destination
    if st.session_state.destination_selected:
        st.success(f"✓ {st.session_state.destination_selected['name']}")
    
    st.markdown("---")
    
    # Date and Time
    st.subheader("🕐 When?")
    time_option = st.radio("Travel time:", ["Leave now", "Arrive by", "Depart at"])
    
    if time_option != "Leave now":
        journey_date = st.date_input("Date:", datetime.now())
        journey_time = st.time_input("Time:", datetime.now().time())
        journey_datetime = datetime.combine(journey_date, journey_time)
    
    # Travel Preferences
    st.subheader("⚙️ Preferences")
    modes = st.multiselect(
        "Transport modes:",
        ["tube", "bus", "dlr", "overground", "elizabeth-line", "national-rail", "walking"],
        default=["tube", "bus", "walking"]
    )
    
    accessibility = st.checkbox("♿ Step-free access only")
    
    st.markdown("---")
    search_button = st.button("🔍 Find Routes", type="primary", use_container_width=True)

# Main content area
if search_button:
    if not st.session_state.origin_selected or not st.session_state.destination_selected:
        st.error("⚠️ Please select both origin and destination from the suggestions")
    else:
        with st.spinner("Finding best routes..."):
            try:
                origin_loc = st.session_state.origin_selected
                dest_loc = st.session_state.destination_selected
                
                if origin_loc.get('lat') and origin_loc.get('lon'):
                    origin_str = f"{origin_loc['lat']},{origin_loc['lon']}"
                else:
                    origin_str = origin_loc['name']
                
                if dest_loc.get('lat') and dest_loc.get('lon'):
                    dest_str = f"{dest_loc['lat']},{dest_loc['lon']}"
                else:
                    dest_str = dest_loc['name']
                
                url = f"{TFL_BASE_URL}/Journey/JourneyResults/{origin_str}/to/{dest_str}"
                
                params = {
                    "app_key": TFL_APP_KEY,
                    "mode": ",".join(modes)
                }
                
                if time_option == "Arrive by":
                    params["timeIs"] = "Arriving"
                    params["date"] = journey_datetime.strftime("%Y%m%d")
                    params["time"] = journey_datetime.strftime("%H%M")
                elif time_option == "Depart at":
                    params["timeIs"] = "Departing"
                    params["date"] = journey_datetime.strftime("%Y%m%d")
                    params["time"] = journey_datetime.strftime("%H%M")
                
                if accessibility:
                    params["accessibilityPreference"] = "StepFreeAccess"
                
                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if "journeys" in data and data["journeys"]:
                    st.success(f"✅ Found {len(data['journeys'])} route options")
                    
                    st.markdown(f"### From: **{origin_loc['name']}** → To: **{dest_loc['name']}**")
                    
                    for idx, journey in enumerate(data["journeys"][:3], 1):
                        with st.expander(f"🗺️ Route {idx} - {journey['duration']} mins", expanded=(idx==1)):
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("⏱️ Duration", f"{journey['duration']} mins")
                            with col2:
                                arrival_time = datetime.fromisoformat(journey['arrivalDateTime'].replace('Z', '+00:00'))
                                st.metric("🕐 Arrives", arrival_time.strftime("%H:%M"))
                            with col3:
                                st.metric("🔄 Changes", len(journey.get('legs', [])) - 1)
                            with col4:
                                departure_time = datetime.fromisoformat(journey['startDateTime'].replace('Z', '+00:00'))
                                st.metric("🚀 Departs", departure_time.strftime("%H:%M"))
                            
                            st.markdown("---")
                            
                            for leg_idx, leg in enumerate(journey.get('legs', []), 1):
                                mode = leg.get('mode', {}).get('name', 'Unknown')
                                
                                mode_icons = {
                                    'tube': '🚇',
                                    'bus': '🚌',
                                    'walking': '🚶',
                                    'dlr': '🚊',
                                    'overground': '🚈',
                                    'elizabeth-line': '🚆',
                                    'national-rail': '🚂'
                                }
                                icon = mode_icons.get(leg.get('mode', {}).get('id', ''), '🚉')
                                
                                st.markdown(f"### {icon} Step {leg_idx}: {mode.title()}")
                                
                                if 'departurePoint' in leg:
                                    st.write(f"**From:** {leg['departurePoint'].get('commonName', 'N/A')}")
                                
                                if 'instruction' in leg:
                                    summary = leg['instruction'].get('summary', '')
                                    detailed = leg['instruction'].get('detailed', '')
                                    st.write(f"*{summary}*")
                                    if detailed and detailed != summary:
                                        st.caption(detailed)
                                
                                leg_duration = leg.get('duration', 0)
                                if leg_duration:
                                    st.write(f"⏱️ {leg_duration} minutes")
                                
                                if 'arrivalPoint' in leg:
                                    st.write(f"**To:** {leg['arrivalPoint'].get('commonName', 'N/A')}")
                                
                                if leg_idx < len(journey.get('legs', [])):
                                    st.markdown("⬇️")
                            
                            if 'fare' in journey:
                                st.markdown("---")
                                st.markdown("### 💷 Fare Information")
                                fare = journey['fare']
                                if 'totalCost' in fare:
                                    st.write(f"**Total Cost:** £{fare['totalCost']/100:.2f}")
                else:
                    st.warning("⚠️ No routes found. Please try different locations or preferences.")
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 300:
                    st.error("❌ Multiple locations found. Please select from the suggestions.")
                else:
                    st.error(f"❌ API Error: {e.response.status_code}")
                    with st.expander("Error details"):
                        st.code(e.response.text)
            except Exception as e:
                st.error(f"❌ An error occurred: {str(e)}")
else:
    st.info("👈 Enter your journey details in the sidebar to get started")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 🎯 How to use:
        1. **Type** your origin (at least 2 characters)
        2. **Select** from suggestions (stations, landmarks, postcodes)
        3. **Choose** your destination the same way
        4. **Pick** your travel time preferences
        5. **Click** 'Find Routes' to see options
        """)
    
    with col2:
        st.markdown("""
        ### 📝 You can search for:
        - 🚇 **Stations**: "King's Cross", "Waterloo"
        - 🏛️ **Landmarks**: "Tower Bridge", "Big Ben"
        - 📮 **Postcodes**: "SW1A 1AA", "EC2M 7PP"
        - 🏢 **Addresses**: "10 Downing Street"
        - 🚏 **Bus stops**: Search by name or code
        """)
    
    st.markdown("---")
    st.markdown("""
    ### 🔑 Setup Required:
    You'll need a free TfL API key from: **https://api-portal.tfl.gov.uk/**
    
    Set it as an environment variable `TFL_APP_KEY` or in Streamlit secrets.
    """)

st.markdown("---")
st.caption("Powered by Transport for London Unified API | Data updated in real-time")
