# tfl_journey_planner.py
# Streamlit TfL Journey Planner — friendly accessibility, robust selection, URL-encoding, smart fallbacks

import streamlit as st
import requests
from datetime import datetime
import os
import re
from urllib.parse import quote

# ────────────────────────────────────────────────────────────────────────────────
# Config
# ────────────────────────────────────────────────────────────────────────────────
TFL_APP_KEY = os.environ.get("TFL_APP_KEY", "your_app_key_here")
TFL_BASE_URL = "https://api.tfl.gov.uk"
REQUEST_TIMEOUT = 10

st.set_page_config(page_title="TfL Journey Planner", page_icon="🚇", layout="wide")
st.title("🚇 Transport for London Journey Planner")
st.markdown("Plan your journey across London using real-time TfL data")

# ────────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────────
def is_postcode(text: str) -> bool:
    """Check if text looks like a UK postcode."""
    if not text:
        return False
    pattern = r'^[A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2}$'
    return bool(re.match(pattern, text.upper().strip()))

def geocode_address(address: str):
    """Geocode address via OpenStreetMap (Nominatim). Returns selection-like dict or None."""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": f"{address}, London, UK",
            "format": "json",
            "limit": 1
        }
        headers = {"User-Agent": "TfL-Journey-Planner-App"}
        resp = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 429:
            # Rate limited; return None silently (the app will try other paths)
            return None
        resp.raise_for_status()
        results = resp.json()
        if results:
            r0 = results[0]
            return {
                "name": address,
                "display": r0.get("display_name", address)[:100],
                "lat": float(r0.get("lat")),
                "lon": float(r0.get("lon")),
                "type": "Address",
                "use_coords": True,
            }
    except Exception:
        pass
    return None

def search_locations(query: str):
    """Search places via TfL 'Place/Search'."""
    if not query or len(query) < 3:
        return []
    try:
        url = f"{TFL_BASE_URL}/Place/Search"
        params = {"query": query, "app_key": TFL_APP_KEY, "maxResults": 10}
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        results = resp.json()
        out = []
        for place in results:
            name = place.get("name", "")
            place_type = place.get("placeType", "")
            lat, lon = place.get("lat"), place.get("lon")
            out.append({
                "display": f"{name} ({place_type})" if place_type else name,
                "name": name,
                "type": place_type or "Place",
                "lat": lat,
                "lon": lon,
                "id": place.get("id", ""),
                "use_coords": bool(lat and lon),
            })
        return out
    except Exception:
        return []

def search_stoppoints(query: str):
    """Search stops via TfL 'StopPoint/Search'."""
    if not query or len(query) < 2:
        return []
    try:
        url = f"{TFL_BASE_URL}/StopPoint/Search"
        params = {"query": query, "app_key": TFL_APP_KEY, "maxResults": 10}
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        out = []
        for match in data.get("matches", []):
            name = match.get("name", "")
            modes = ", ".join(match.get("modes", []))
            lat, lon = match.get("lat"), match.get("lon")
            out.append({
                "display": f"{name} [{modes}]" if modes else name,
                "name": name,
                "type": "Stop",
                "lat": lat,
                "lon": lon,
                "id": match.get("id", ""),
                "use_coords": bool(lat and lon),
            })
        return out
    except Exception:
        return []

def resolve_location(query_text: str):
    """Resolve free text into a selection-like dict. Prefers TfL matches, then geocode."""
    if not query_text:
        return None

    # Postcode quick path
    if is_postcode(query_text):
        return {
            "name": query_text.upper(),
            "display": query_text.upper(),
            "type": "Postcode",
            "use_coords": False,
        }

    # TfL searches (prefer coordinates if present)
    places = search_locations(query_text)
    stops = search_stoppoints(query_text)
    candidates = places + stops
    if candidates:
        return candidates[0]

    # Geocode fallback
    return geocode_address(query_text)

# Keep widget ↔ state in sync when selecting/clicking suggestions
def _select_origin(name: str, payload: dict):
    st.session_state.origin_selected = payload
    st.session_state.origin_query = name
    st.session_state.origin_input = name  # sync text_input widget
    st.rerun()

def _select_destination(name: str, payload: dict):
    st.session_state.destination_selected = payload
    st.session_state.destination_query = name
    st.session_state.destination_input = name  # sync text_input widget
    st.rerun()

# ────────────────────────────────────────────────────────────────────────────────
# Session state init
# ────────────────────────────────────────────────────────────────────────────────
for key, default in [
    ("origin_selected", None),
    ("destination_selected", None),
    ("origin_query", ""),
    ("destination_query", ""),
    # origin_input / destination_input are created by text_input via key=..., but
    # having defaults here avoids None issues on first run if accessed directly.
    ("origin_input", ""),
    ("destination_input", ""),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ────────────────────────────────────────────────────────────────────────────────
# Sidebar UI
# ────────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Journey Details")

    # ── Origin ──────────────────────────────────────────────────────────────────
    st.subheader("📍 From")
    origin_input = st.text_input(
        "Origin:",
        value=st.session_state.origin_input,
        placeholder="Station, postcode, or address",
        key="origin_input"
    )

    # Auto-clear stale selection if user edits text
    if st.session_state.origin_selected and origin_input != st.session_state.origin_selected.get("name", ""):
        st.session_state.origin_selected = None

    if origin_input and len(origin_input) >= 2:
        # Update query mirror used by auto-resolve
        if origin_input != st.session_state.origin_query:
            st.session_state.origin_query = origin_input

        with st.spinner("Searching..."):
            found_something = False

            # Postcode quick-pick
            if is_postcode(origin_input):
                found_something = True
                st.markdown("**📮 Postcode:**")
                if st.button(
                    f"📍 {origin_input.upper()}",
                    key="origin_postcode",
                    use_container_width=True,
                    type="primary"
                ):
                    _select_origin(
                        origin_input.upper(),
                        {
                            "name": origin_input.upper(),
                            "display": origin_input.upper(),
                            "type": "Postcode",
                            "use_coords": False,
                        },
                    )

            # TfL suggestions (Place + StopPoint)
            place_suggestions = search_locations(origin_input)
            stop_suggestions = search_stoppoints(origin_input)
            all_suggestions = place_suggestions + stop_suggestions

            # Deduplicate by name while keeping first occurrence
            seen = set()
            unique_suggestions = []
            for s in all_suggestions:
                n = s.get("name", "")
                if n and n not in seen:
                    seen.add(n)
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
                        _select_origin(suggestion["name"], suggestion)

            # Geocode fallback (if not a postcode)
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
                        _select_origin(origin_input, geocoded)

            if not found_something:
                st.warning("⚠️ Location not found")
                st.info("Try: 'Euston', 'NW1 2JH', or 'London Eye'")

    if st.session_state.origin_selected:
        st.success(f"✓ {st.session_state.origin_selected['name']}")
        if st.button("❌ Clear", key="clear_origin", use_container_width=True):
            st.session_state.origin_selected = None
            st.session_state.origin_query = ""
            st.session_state.origin_input = ""  # clear widget too
            st.rerun()

    st.markdown("---")

    # ── Destination ─────────────────────────────────────────────────────────────
    st.subheader("📍 To")
    destination_input = st.text_input(
        "Destination:",
        value=st.session_state.destination_input,
        placeholder="Station, postcode, or address",
        key="destination_input"
    )

    # Auto-clear stale selection if user edits text
    if st.session_state.destination_selected and destination_input != st.session_state.destination_selected.get("name", ""):
        st.session_state.destination_selected = None

    if destination_input and len(destination_input) >= 2:
        if destination_input != st.session_state.destination_query:
            st.session_state.destination_query = destination_input

        with st.spinner("Searching..."):
            found_something = False

            # Postcode quick-pick
            if is_postcode(destination_input):
                found_something = True
                st.markdown("**📮 Postcode:**")
                if st.button(
                    f"📍 {destination_input.upper()}",
                    key="dest_postcode",
                    use_container_width=True,
                    type="primary"
                ):
                    _select_destination(
                        destination_input.upper(),
                        {
                            "name": destination_input.upper(),
                            "display": destination_input.upper(),
                            "type": "Postcode",
                            "use_coords": False,
                        },
                    )

            # TfL suggestions
            place_suggestions = search_locations(destination_input)
            stop_suggestions = search_stoppoints(destination_input)
            all_suggestions = place_suggestions + stop_suggestions

            seen = set()
            unique_suggestions = []
            for s in all_suggestions:
                n = s.get("name", "")
                if n and n not in seen:
                    seen.add(n)
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
                        _select_destination(suggestion["name"], suggestion)

            # Geocode fallback
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
                        _select_destination(destination_input, geocoded)

            if not found_something:
                st.warning("⚠️ Location not found")
                st.info("Try: 'Liverpool Street', 'EC2M 7PP', or 'Tower Bridge'")

    if st.session_state.destination_selected:
        st.success(f"✓ {st.session_state.destination_selected['name']}")
        if st.button("❌ Clear", key="clear_dest", use_container_width=True):
            st.session_state.destination_selected = None
            st.session_state.destination_query = ""
            st.session_state.destination_input = ""  # clear widget too
            st.rerun()

    st.markdown("---")

    # ── Time ────────────────────────────────────────────────────────────────────
    st.subheader("🕐 When?")
    time_option = st.radio("Travel time:", ["Leave now", "Arrive by", "Depart at"])
    if time_option != "Leave now":
        # default to now; users can tweak date/time
        journey_date = st.date_input("Date:", datetime.now())
        journey_time = st.time_input("Time:", datetime.now().time())
        journey_datetime = datetime.combine(journey_date, journey_time)

    # ── Preferences ─────────────────────────────────────────────────────────────
    st.subheader("⚙️ Preferences")
    modes = st.multiselect(
        "Transport modes:",
        ["tube", "bus", "dlr", "overground", "elizabeth-line", "national-rail", "walking"],
        default=["tube", "bus", "walking"]
    )

    # Friendly Accessibility labels → TfL enum values
    ACCESSIBILITY_LABELS_TO_VALUES = {
        "No Requirements": "NoRequirements",
        "No Solid Stairs": "NoSolidStairs",
        "No Escalators": "NoEscalators",
        "No Elevators": "NoElevators",
        "Step-free to Vehicle": "StepFreeToVehicle",
        "Step-free to Platform": "StepFreeToPlatform",
    }
    ACCESSIBILITY_DISPLAY_ORDER = list(ACCESSIBILITY_LABELS_TO_VALUES.keys())

    accessibility_selected_labels = st.multiselect(
        "♿ Accessibility preferences:",
        ACCESSIBILITY_DISPLAY_ORDER,
        default=[],
        help="Choose one or more preferences. Combinations are supported by TfL."
    )

    st.markdown("---")
    search_button = st.button("🔍 Find Routes", type="primary", use_container_width=True)

# ────────────────────────────────────────────────────────────────────────────────
# Main: perform search
# ────────────────────────────────────────────────────────────────────────────────
if search_button:
    # Auto-resolve if the user typed but didn't click a suggestion
    if not st.session_state.origin_selected and st.session_state.origin_query:
        st.session_state.origin_selected = resolve_location(st.session_state.origin_query)
    if not st.session_state.destination_selected and st.session_state.destination_query:
        st.session_state.destination_selected = resolve_location(st.session_state.destination_query)

    if not st.session_state.origin_selected or not st.session_state.destination_selected:
        st.error("⚠️ Please select valid origin and destination (or choose from suggestions).")
    else:
        with st.spinner("Finding best routes..."):
            try:
                origin_loc = st.session_state.origin_selected
                dest_loc = st.session_state.destination_selected

                # Build origin/destination strings (prefer coordinates for accuracy)
                if origin_loc.get("use_coords") and origin_loc.get("lat") and origin_loc.get("lon"):
                    origin_str = f"{origin_loc['lat']},{origin_loc['lon']}"
                else:
                    origin_str = origin_loc["name"]

                if dest_loc.get("use_coords") and dest_loc.get("lat") and dest_loc.get("lon"):
                    dest_str = f"{dest_loc['lat']},{dest_loc['lon']}"
                else:
                    dest_str = dest_loc["name"]

                # URL-encode in case of special characters like "/"
                origin_encoded = quote(origin_str, safe="")
                dest_encoded = quote(dest_str, safe="")

                url = f"{TFL_BASE_URL}/Journey/JourneyResults/{origin_encoded}/to/{dest_encoded}"
                params = {
                    "app_key": TFL_APP_KEY,
                    "mode": ",".join(modes) if modes else "tube,walking",
                }

                if time_option == "Arrive by":
                    params["timeIs"] = "Arriving"
                    params["date"] = journey_datetime.strftime("%Y%m%d")
                    params["time"] = journey_datetime.strftime("%H%M")
                elif time_option == "Depart at":
                    params["timeIs"] = "Departing"
                    params["date"] = journey_datetime.strftime("%Y%m%d")
                    params["time"] = journey_datetime.strftime("%H%M")

                if accessibility_selected_labels:
                    selected_values = [ACCESSIBILITY_LABELS_TO_VALUES[l] for l in accessibility_selected_labels]
                    params["accessibilityPreference"] = ",".join(selected_values)

                resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()

                if data.get("journeys"):
                    st.success(f"✅ Found {len(data['journeys'])} route options")
                    st.markdown(f"### From: **{origin_loc['name']}** → To: **{dest_loc['name']}**")

                    for idx, journey in enumerate(data["journeys"][:3], 1):
                        with st.expander(f"🗺️ Route {idx} – {journey['duration']} mins", expanded=(idx == 1)):
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("⏱️ Duration", f"{journey['duration']} mins")
                            with col2:
                                arrival = datetime.fromisoformat(journey['arrivalDateTime'].replace('Z', '+00:00'))
                                st.metric("🕐 Arrives", arrival.strftime("%H:%M"))
                            with col3:
                                st.metric("🔄 Changes", max(len(journey.get('legs', [])) - 1, 0))
                            with col4:
                                departure = datetime.fromisoformat(journey['startDateTime'].replace('Z', '+00:00'))
                                st.metric("🚀 Departs", departure.strftime("%H:%M"))

                            st.markdown("---")

                            for leg_idx, leg in enumerate(journey.get("legs", []), 1):
                                mode_id = leg.get("mode", {}).get("id", "")
                                mode_name = leg.get("mode", {}).get("name", "Unknown")
                                mode_icons = {
                                    "tube": "🚇", "bus": "🚌", "walking": "🚶",
                                    "dlr": "🚊", "overground": "🚈",
                                    "elizabeth-line": "🚆", "national-rail": "🚂"
                                }
                                icon = mode_icons.get(mode_id, "🚉")
                                st.markdown(f"### {icon} Step {leg_idx}: {mode_name.title()}")

                                if "departurePoint" in leg:
                                    st.write(f"**From:** {leg['departurePoint'].get('commonName', 'N/A')}")
                                if "instruction" in leg:
                                    st.write(f"*{leg['instruction'].get('summary', '')}*")
                                if leg.get("duration"):
                                    st.write(f"⏱️ {leg['duration']} minutes")
                                if "arrivalPoint" in leg:
                                    st.write(f"**To:** {leg['arrivalPoint'].get('commonName', 'N/A')}")

                                if leg_idx < len(journey.get("legs", [])):
                                    st.markdown("⬇️")

                            if journey.get("fare", {}).get("totalCost") is not None:
                                st.markdown("---")
                                st.markdown("### 💷 Fare")
                                st.write(f"**Total:** £{journey['fare']['totalCost']/100:.2f}")
                else:
                    st.warning("⚠️ No routes found. Try different locations or modes.")

            except requests.exceptions.HTTPError as e:
                st.error(f"❌ API Error: {e.response.status_code}")
                with st.expander("Details"):
                    try:
                        st.code(e.response.text)
                    except Exception:
                        st.write("No error body available.")
            except requests.exceptions.Timeout:
                st.error("⏱️ Request timed out. Please try again.")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

else:
    st.info("👈 Enter journey details to get started")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        ### 🎯 How to use
        1. Enter origin (station/postcode/address)
        2. Pick from suggestions (or just type)
        3. Enter destination
        4. Set time & preferences
        5. Click **Find Routes**
        """)
    with col2:
        st.markdown("""
        ### 📝 Examples
        - 🚇 **Stations**: "Euston", "King's Cross"
        - 📮 **Postcodes**: "NW1 2JH", "EC2M 7PP"
        - 🏛️ **Landmarks**: "Tower Bridge"
        - 🏢 **Addresses**: Any London address
        """)

    st.markdown("---")
    st.caption("Get your TfL API key at: https://api-portal.tfl.gov.uk/")

st.markdown("---")
st.caption("Powered by TfL Unified API")
