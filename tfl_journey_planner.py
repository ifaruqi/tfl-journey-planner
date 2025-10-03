# tfl_journey_planner.py
# Streamlit TfL Journey Planner — friendly accessibility, robust selection, URL-encoding,
# London-time handling, graceful 404, and simple main-page sorting over all journeys.

import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import re
from urllib.parse import quote

# ────────────────────────────────────────────────────────────────────────────────
# Config
# ────────────────────────────────────────────────────────────────────────────────
TFL_APP_KEY = os.environ.get("TFL_APP_KEY", "your_app_key_here")
TFL_BASE_URL = "https://api.tfl.gov.uk"
REQUEST_TIMEOUT = 10
UK_TZ = ZoneInfo("Europe/London")

st.set_page_config(page_title="TfL Journey Planner", page_icon="🚇", layout="wide")
st.title("🚇 Transport for London Journey Planner")
st.markdown("Plan your journey across London using real-time TfL data")
st.caption("🕒 Note: All times shown here refer to **London time (Europe/London)**.")

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
        params = {"q": f"{address}, London, UK", "format": "json", "limit": 1}
        headers = {"User-Agent": "TfL-Journey-Planner-App"}
        resp = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 429:
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
    if is_postcode(query_text):
        return {"name": query_text.upper(), "display": query_text.upper(), "type": "Postcode", "use_coords": False}
    places = search_locations(query_text)
    stops = search_stoppoints(query_text)
    candidates = places + stops
    if candidates:
        return candidates[0]
    return geocode_address(query_text)

# Safe way to programmatically change a text_input's value:
# set *_pending, then rerun; on next run, apply pending BEFORE widget is created.
def _select_origin(name: str, payload: dict):
    st.session_state.origin_selected = payload
    st.session_state.origin_query = name
    st.session_state.origin_input_pending = name
    st.rerun()

def _select_destination(name: str, payload: dict):
    st.session_state.destination_selected = payload
    st.session_state.destination_query = name
    st.session_state.destination_input_pending = name
    st.rerun()

def request_journeys(url, params):
    """Call TfL JourneyResults and return (json, error_info). error_info is None on success."""
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 404:
            # Gracefully handle the common 'No journey found'
            try:
                err = resp.json()
            except Exception:
                err = {"message": "No journey found for your inputs."}
            return None, {"status": 404, "message": err.get("message", "No journey found.")}
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.HTTPError as e:
        try:
            err_body = e.response.json()
            msg = err_body.get("message") or e.response.text
        except Exception:
            msg = str(e)
        return None, {"status": e.response.status_code if e.response else None, "message": msg}
    except requests.exceptions.Timeout:
        return None, {"status": "timeout", "message": "Request timed out."}
    except Exception as e:
        return None, {"status": "exception", "message": str(e)}

# ────────────────────────────────────────────────────────────────────────────────
# Session state init
# ────────────────────────────────────────────────────────────────────────────────
for key, default in [
    ("origin_selected", None),
    ("destination_selected", None),
    ("origin_query", ""),
    ("destination_query", ""),
    ("origin_input", ""),
    ("destination_input", ""),
    ("journey_time_option", "Leave now"),
    ("journey_datetime_uk", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# Apply any pending text updates BEFORE creating widgets
if "origin_input_pending" in st.session_state:
    st.session_state.origin_input = st.session_state.origin_input_pending
    del st.session_state["origin_input_pending"]

if "destination_input_pending" in st.session_state:
    st.session_state.destination_input = st.session_state.destination_input_pending
    del st.session_state["destination_input_pending"]

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
                        {"name": origin_input.upper(), "display": origin_input.upper(), "type": "Postcode", "use_coords": False},
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
                for idx, suggestion in enumerate(unique_suggestions[:10]):
                    if st.button(
                        f"{suggestion['display'][:70]}",
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
            st.session_state.origin_input_pending = ""   # clear via pending → safe
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
                        {"name": destination_input.upper(), "display": destination_input.upper(), "type": "Postcode", "use_coords": False},
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
                for idx, suggestion in enumerate(unique_suggestions[:10]):
                    if st.button(
                        f"{suggestion['display'][:70]}",
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
            st.session_state.destination_input_pending = ""  # clear via pending → safe
            st.rerun()

    st.markdown("---")

    # ── Time (Europe/London) ────────────────────────────────────────────────────
    st.subheader("🕐 When?")
    uk_now = datetime.now(UK_TZ)

    time_option = st.radio("Travel time:", ["Leave now", "Arrive by", "Depart at"])
    st.session_state.journey_time_option = time_option

    if time_option != "Leave now":
        journey_date = st.date_input("Date:", uk_now.date(), key="jp_date")
        journey_time = st.time_input(
            "Time:",
            uk_now.time().replace(second=0, microsecond=0),
            key="jp_time"
        )
        # Make a TZ-aware datetime in Europe/London
        st.session_state.journey_datetime_uk = datetime.combine(
            journey_date, journey_time, tzinfo=UK_TZ
        )
    else:
        st.session_state.journey_datetime_uk = None

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
            origin_loc = st.session_state.origin_selected
            dest_loc = st.session_state.destination_selected

            # Build origin/destination strings (prefer coordinates for accuracy)
            origin_str = (
                f"{origin_loc['lat']},{origin_loc['lon']}"
                if origin_loc.get("use_coords") and origin_loc.get("lat") and origin_loc.get("lon")
                else origin_loc["name"]
            )
            dest_str = (
                f"{dest_loc['lat']},{dest_loc['lon']}"
                if dest_loc.get("use_coords") and dest_loc.get("lat") and dest_loc.get("lon")
                else dest_loc["name"]
            )

            # URL-encode in case of special characters like "/"
            origin_encoded = quote(origin_str, safe="")
            dest_encoded = quote(dest_str, safe="")
            url = f"{TFL_BASE_URL}/Journey/JourneyResults/{origin_encoded}/to/{dest_encoded}"

            # Base params
            params = {
                "app_key": TFL_APP_KEY,
                "mode": ",".join(modes) if modes else "tube,walking",
            }

            # Time params (lowercase timeIs; limit search direction)
            time_option = st.session_state.get("journey_time_option", "Leave now")
            journey_datetime_uk = st.session_state.get("journey_datetime_uk")

            if time_option == "Arrive by" and journey_datetime_uk:
                params["timeIs"] = "arriving"  # must be lowercase
                params["date"] = journey_datetime_uk.strftime("%Y%m%d")
                params["time"] = journey_datetime_uk.strftime("%H%M")
                params["calcOneDirection"] = "true"
            elif time_option == "Depart at" and journey_datetime_uk:
                params["timeIs"] = "departing"  # must be lowercase
                params["date"] = journey_datetime_uk.strftime("%Y%m%d")
                params["time"] = journey_datetime_uk.strftime("%H%M")
                params["calcOneDirection"] = "true"
            # else: Leave now → omit date/time to use current time

            # Accessibility
            selected_values = []
            if accessibility_selected_labels:
                selected_values = [ACCESSIBILITY_LABELS_TO_VALUES[l] for l in accessibility_selected_labels]
                params["accessibilityPreference"] = ",".join(selected_values)

            # First attempt
            data, err = request_journeys(url, params)

            # If no journey found (404) and we had accessibility filters, retry once without them
            relaxed = False
            if err and err.get("status") == 404 and selected_values:
                relaxed = True
                params_relaxed = dict(params)
                params_relaxed.pop("accessibilityPreference", None)
                data, err = request_journeys(url, params_relaxed)

            # Present results / messages
            if data and data.get("journeys"):
                if relaxed:
                    st.info("ℹ️ No journeys matched the accessibility filters, so I tried again without them and found options.")
                st.success(f"✅ Found {len(data['journeys'])} route options")
                st.markdown(f"### From: **{origin_loc['name']}** → To: **{dest_loc['name']}**")
                st.caption("🕒 All times below are shown in **London time**.")

                # ── Simple sorting (MAIN PAGE) ──────────────────────────────────
                with st.expander("🔎 Sort results", expanded=True):
                    sort_option = st.radio(
                        "Sort by",
                        ["Fastest", "Cheapest", "Least Walking"],
                        index=0,
                        horizontal=True,
                    )

                # Helper metrics for sorting display
                def walking_minutes(j):
                    total = 0
                    for leg in (j.get("legs") or []):
                        if leg.get("mode", {}).get("id") == "walking":
                            total += int(leg.get("duration", 0) or 0)
                    return total

                def journey_changes(j):
                    legs = j.get("legs", []) or []
                    return max(len(legs) - 1, 0)

                def fare_pence(j):
                    return j.get("fare", {}).get("totalCost")  # may be None

                # Sort ALL journeys according to selection
                journeys = data.get("journeys", [])

                def sort_key(j):
                    dur  = j.get("duration", 10**9)
                    chg  = journey_changes(j)
                    walk = walking_minutes(j)
                    fare = fare_pence(j)
                    fare_sort = fare if isinstance(fare, int) else 10**9  # missing fare → last

                    if sort_option == "Cheapest":
                        return (fare_sort, dur, chg, walk)
                    if sort_option == "Least Walking":
                        return (walk, dur, chg)
                    # Fastest (default)
                    return (dur, chg, walk)

                sorted_journeys = sorted(journeys, key=sort_key)

                if not sorted_journeys:
                    st.warning("No routes available for these inputs.")
                else:
                    st.caption(f"Sorted by **{sort_option}** · Showing **{len(sorted_journeys)}** routes")

                # ── Render journeys (all, in sorted order) ─────────────────────
                for idx, journey in enumerate(sorted_journeys, 1):
                    with st.expander(f"🗺️ Route {idx} – {journey['duration']} mins", expanded=(idx == 1)):
                        # Convert ISO strings (UTC) → London time for display
                        arr_utc = datetime.fromisoformat(journey['arrivalDateTime'].replace('Z', '+00:00'))
                        dep_utc = datetime.fromisoformat(journey['startDateTime'].replace('Z', '+00:00'))
                        arr_uk = arr_utc.astimezone(UK_TZ)
                        dep_uk = dep_utc.astimezone(UK_TZ)

                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("⏱️ Duration", f"{journey['duration']} mins")
                        with col2:
                            st.metric("🕐 Arrives", arr_uk.strftime("%H:%M"))
                        with col3:
                            st.metric("🔄 Changes", journey_changes(journey))
                        with col4:
                            st.metric("🚶 Walking", f"{walking_minutes(journey)} min")

                        st.caption(f"Date: {dep_uk.strftime('%a, %d %b %Y')} (London)")
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
                # Friendly messaging on 404 / empty or other errors
                if err and err.get("status") == 404:
                    if locals().get("relaxed"):
                        st.warning("⚠️ No journeys found even after relaxing accessibility filters.")
                    else:
                        st.warning("⚠️ No journeys found for your inputs.")
                    with st.expander("Try these tips"):
                        st.markdown(
                            "- Pick nearby stations or landmarks instead of precise addresses\n"
                            "- Adjust **time** (late night services may be limited)\n"
                            "- Include more **modes** (e.g., bus / walking)\n"
                            "- Remove **accessibility filters** if possible and try again\n"
                            "- Check for planned closures or disruptions on lines"
                        )
                elif err:
                    st.error(f"❌ Request failed ({err.get('status')}): {err.get('message')}")
                    with st.expander("Technical details"):
                        st.code(err.get("message", ""), language="text")
                else:
                    st.warning("⚠️ No routes found. Try different locations or modes.")

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
st.caption("Powered by TfL Unified API • All times shown are London time (Europe/London).")
