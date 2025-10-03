# Add this at the top with other imports
from urllib.parse import quote

# Then find the journey search section and update it
app_code = '''import streamlit as st
import requests
from datetime import datetime, timedelta
import os
import re
from urllib.parse import quote

# TfL API Configuration
TFL_APP_KEY = os.environ.get("TFL_APP_KEY", "your_app_key_here")
TFL_BASE_URL = "https://api.tfl.gov.uk"

st.set_page_config(page_title="TfL Journey Planner", page_icon="🚇", layout="wide")

def is_postcode(text):
    """Check if text looks like a UK postcode"""
    pattern = r'^[A-Z]{1,2}[0-9][A-Z0-9]?\\s?[0-9][A-Z]{2}$'
    return bool(re.match(pattern, text.upper().strip()))

def geocode_address(address):
    """Geocode addresses using OpenStreetMap"""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": f"{address}, London, UK",
            "format": "json",
            "limit": 1
        }
        headers = {"User-Agent": "TfL-Journey-Planner-App"}
        
        response = requests.get(url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        results = response.json()
        
        if results and len(results) > 0:
            result = results[0]
            return {
                'name': address,
                'display': result.get('display_name', address)[:100],
                'lat': float(result.get('lat')),
                'lon': float(result.get('lon')),
                'type': 'Address',
                'use_coords': True
            }
    except:
        pass
    return None

def search_locations(query):
    """Search for locations using TfL API"""
    if not query or len(query) < 3:
        return []
    
    try:
        url = f"{TFL_BASE_URL}/Place/Search"
        params = {"query": query, "app_key": TFL_APP_KEY, "maxResults": 10}
        
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 404:
            return []
        
        response.raise_for_status()
        results = response.json()
        
        suggestions = []
        for place in results:
            name = place.get('name', '')
            place_type = place.get('placeType', '')
            lat = place.get('lat')
            lon = place.get('lon')
            
            suggestions.append({
                'display': f"{name} ({place_type})" if place_type else name,
                'name': name,
                'type': place_type,
                'lat': lat,
                'lon': lon,
                'id': place.get('id', ''),
                'use_coords': bool(lat and lon)  # Use coords if available for better accuracy
            })
        
        return suggestions
    except:
        return []

def search_stoppoints(query):
    """Search for transport stops"""
    if not query or len(query) < 2:
        return []
    
    try:
        url = f"{TFL_BASE_URL}/StopPoint/Search"
        params = {"query": query, "app_key": TFL_APP_KEY, "maxResults": 10}
        
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 404:
            return []
            
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
                    'use_coords': bool(lat and lon)
                })
        
        return suggestions
    except:
        return []

st.title("🚇 Transport for London Journey Planner")
st.markdown("Plan your journey across London using real-time TfL data")

# Initialize session state
if 'origin_selected' not in st.session_state:
    st.session_state.origin_selected = None
if 'destination_selected' not in st.session_state:
    st.session_state.destination_selected = None
if 'origin_query' not in st.session_state:
    st.session_state.origin_query = ""
if 'destination_query' not in st.session_state:
    st.session_state.destination_query = ""

# Sidebar
with st.sidebar:
    st.header("Journey Details")
    
    # Origin
    st.subheader("📍 From")
    origin_input = st.text_input(
        "Origin:",
        value=st.session_state.origin_query,
        placeholder="Station, postcode, or address",
        key="origin_input"
    )
    
    if origin_input and len(origin_input) >= 2:
        if origin_input != st.session_state.origin_query or st.session_state.origin_selected is None:
            st.session_state.origin_query = origin_input
            
            with st.spinner("Searching..."):
                found_something = False
                
                # Check if it's a postcode
                if is_postcode(origin_input):
                    found_something = True
                    st.markdown("**📮 Postcode:**")
                    if st.button(
                        f"📍 {origin_input.upper()}",
                        key="origin_postcode",
                        use_container_width=True,
                        type="primary"
                    ):
                        st.session_state.origin_selected = {
                            'name': origin_input.upper(),
                            'display': origin_input.upper(),
                            'type': 'Postcode',
                            'use_coords': False
                        }
                        st.session_state.origin_query = origin_input
                        st.rerun()
                
                # Search TfL
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
                    found_something = True
                    st.markdown("**🚇 Stations & Places:**")
                    for idx, suggestion in enumerate(unique_suggestions[:6]):
                        if st.button(
                            f"{suggestion['display'][:60]}",
                            key=f"origin_sugg_{idx}",
                            use_container_width=True
                        ):
                            st.session_state.origin_selected = suggestion
                            st.session_state.origin_query = suggestion['name']
                            st.rerun()
                
                # Geocode fallback
                if not is_postcode(origin_input):
                    geocoded = geocode_address(origin_input)
                    if geocoded:
                        found_something = True
                        st.markdown("**🗺️ Address:**")
                        if st.button(
                            f"📍 {geocoded['display'][:80]}",
                            key="origin_geocoded",
                            use_container_width=True,
                            type="secondary"
                        ):
                            st.session_state.origin_selected = geocoded
                            st.session_state.origin_query = origin_input
                            st.rerun()
                
                if not found_something:
                    st.warning("⚠️ Location not found")
                    st.info("Try: 'Euston', 'NW1 2JH', or 'London Eye'")
    
    if st.session_state.origin_selected:
        st.success(f"✓ {st.session_state.origin_selected['name']}")
        if st.button("❌ Clear", key="clear_origin", use_container_width=True):
            st.session_state.origin_selected = None
            st.session_state.origin_query = ""
            st.rerun()
    
    st.markdown("---")
    
    # Destination
    st.subheader("📍 To")
    destination_input = st.text_input(
        "Destination:",
        value=st.session_state.destination_query,
        placeholder="Station, postcode, or address",
        key="destination_input"
    )
    
    if destination_input and len(destination_input) >= 2:
        if destination_input != st.session_state.destination_query or st.session_state.destination_selected is None:
            st.session_state.destination_query = destination_input
            
            with st.spinner("Searching..."):
                found_something = False
                
                if is_postcode(destination_input):
                    found_something = True
                    st.markdown("**📮 Postcode:**")
                    if st.button(
                        f"📍 {destination_input.upper()}",
                        key="dest_postcode",
                        use_container_width=True,
                        type="primary"
                    ):
                        st.session_state.destination_selected = {
                            'name': destination_input.upper(),
                            'display': destination_input.upper(),
                            'type': 'Postcode',
                            'use_coords': False
                        }
                        st.session_state.destination_query = destination_input
                        st.rerun()
                
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
                    found_something = True
                    st.markdown("**🚇 Stations & Places:**")
                    for idx, suggestion in enumerate(unique_suggestions[:6]):
                        if st.button(
                            f"{suggestion['display'][:60]}",
                            key=f"dest_sugg_{idx}",
                            use_container_width=True
                        ):
                            st.session_state.destination_selected = suggestion
                            st.session_state.destination_query = suggestion['name']
                            st.rerun()
                
                if not is_postcode(destination_input):
                    geocoded = geocode_address(destination_input)
                    if geocoded:
                        found_something = True
                        st.markdown("**🗺️ Address:**")
                        if st.button(
                            f"📍 {geocoded['display'][:80]}",
                            key="dest_geocoded",
                            use_container_width=True,
                            type="secondary"
                        ):
                            st.session_state.destination_selected = geocoded
                            st.session_state.destination_query = destination_input
                            st.rerun()
                
                if not found_something:
                    st.warning("⚠️ Location not found")
                    st.info("Try: 'Liverpool Street', 'EC2M 7PP', or 'Tower Bridge'")
    
    if st.session_state.destination_selected:
        st.success(f"✓ {st.session_state.destination_selected['name']}")
        if st.button("❌ Clear", key="clear_dest", use_container_width=True):
            st.session_state.destination_selected = None
            st.session_state.destination_query = ""
            st.rerun()
    
    st.markdown("---")
    
    # Time
    st.subheader("🕐 When?")
    time_option = st.radio("Travel time:", ["Leave now", "Arrive by", "Depart at"])
    
    if time_option != "Leave now":
        journey_date = st.date_input("Date:", datetime.now())
        journey_time = st.time_input("Time:", datetime.now().time())
        journey_datetime = datetime.combine(journey_date, journey_time)
    
    # Preferences
    st.subheader("⚙️ Preferences")
    modes = st.multiselect(
        "Transport modes:",
        ["tube", "bus", "dlr", "overground", "elizabeth-line", "national-rail", "walking"],
        default=["tube", "bus", "walking"]
    )
    
    accessibility = st.checkbox("♿ Step-free access only")
    
    st.markdown("---")
    search_button = st.button("🔍 Find Routes", type="primary", use_container_width=True)

# Main content
if search_button:
    if not st.session_state.origin_selected or not st.session_state.destination_selected:
        st.error("⚠️ Please select both origin and destination")
    else:
        with st.spinner("Finding best routes..."):
            try:
                origin_loc = st.session_state.origin_selected
                dest_loc = st.session_state.destination_selected
                
                # Determine what to use: coordinates or name
                if origin_loc.get('use_coords') and origin_loc.get('lat') and origin_loc.get('lon'):
                    origin_str = f"{origin_loc['lat']},{origin_loc['lon']}"
                else:
                    origin_str = origin_loc['name']
                
                if dest_loc.get('use_coords') and dest_loc.get('lat') and dest_loc.get('lon'):
                    dest_str = f"{dest_loc['lat']},{dest_loc['lon']}"
                else:
                    dest_str = dest_loc['name']
                
                # URL encode to handle special characters like /
                origin_encoded = quote(origin_str, safe='')
                dest_encoded = quote(dest_str, safe='')
                
                url = f"{TFL_BASE_URL}/Journey/JourneyResults/{origin_encoded}/to/{dest_encoded}"
                
                params = {"app_key": TFL_APP_KEY, "mode": ",".join(modes)}
                
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
                                arrival = datetime.fromisoformat(journey['arrivalDateTime'].replace('Z', '+00:00'))
                                st.metric("🕐 Arrives", arrival.strftime("%H:%M"))
                            with col3:
                                st.metric("🔄 Changes", len(journey.get('legs', [])) - 1)
                            with col4:
                                departure = datetime.fromisoformat(journey['startDateTime'].replace('Z', '+00:00'))
                                st.metric("🚀 Departs", departure.strftime("%H:%M"))
                            
                            st.markdown("---")
                            
                            for leg_idx, leg in enumerate(journey.get('legs', []), 1):
                                mode = leg.get('mode', {}).get('name', 'Unknown')
                                mode_icons = {
                                    'tube': '🚇', 'bus': '🚌', 'walking': '🚶',
                                    'dlr': '🚊', 'overground': '🚈',
                                    'elizabeth-line': '🚆', 'national-rail': '🚂'
                                }
                                icon = mode_icons.get(leg.get('mode', {}).get('id', ''), '🚉')
                                
                                st.markdown(f"### {icon} Step {leg_idx}: {mode.title()}")
                                
                                if 'departurePoint' in leg:
                                    st.write(f"**From:** {leg['departurePoint'].get('commonName', 'N/A')}")
                                
                                if 'instruction' in leg:
                                    st.write(f"*{leg['instruction'].get('summary', '')}*")
                                
                                if leg.get('duration'):
                                    st.write(f"⏱️ {leg['duration']} minutes")
                                
                                if 'arrivalPoint' in leg:
                                    st.write(f"**To:** {leg['arrivalPoint'].get('commonName', 'N/A')}")
                                
                                if leg_idx < len(journey.get('legs', [])):
                                    st.markdown("⬇️")
                            
                            if 'fare' in journey and 'totalCost' in journey['fare']:
                                st.markdown("---")
                                st.markdown("### 💷 Fare")
                                st.write(f"**Total:** £{journey['fare']['totalCost']/100:.2f}")
                else:
                    st.warning("⚠️ No routes found. Try different locations.")
                    
            except requests.exceptions.HTTPError as e:
                st.error(f"❌ API Error: {e.response.status_code}")
                with st.expander("Details"):
                    st.code(e.response.text)
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
else:
    st.info("👈 Enter journey details to get started")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        ### 🎯 How to use:
        1. Enter origin (station/postcode/address)
        2. Select from suggestions
        3. Enter destination
        4. Set preferences
        5. Click 'Find Routes'
        """)
    
    with col2:
        st.markdown("""
        ### 📝 Examples:
        - 🚇 **Stations**: "Euston", "Kings Cross"
        - 📮 **Postcodes**: "NW1 2JH", "EC2M 7PP"
        - 🏛️ **Landmarks**: "Tower Bridge"
        - 🏢 **Addresses**: Any London address
        """)
    
    st.markdown("---")
    st.caption("Get your TfL API key at: https://api-portal.tfl.gov.uk/")

st.markdown("---")
st.caption("Powered by TfL Unified API")
'''

# Save
with open('tfl_journey_planner.py', 'w', encoding='utf-8') as f:
    f.write(app_code)

print("✅ FIXED - URL encoding added!")
print("Now handles special characters like / in place names")
