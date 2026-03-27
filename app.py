import math
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import io

# -------------------------------
# PAGE CONFIG
# -------------------------------
st.set_page_config(page_title="Directional Drilling Tool", layout="wide")

st.title("🛢️ Directional Drilling Calculator")
st.markdown("### Advanced Well Trajectory Analysis")

# -------------------------------
# HELPER FUNCTIONS
# -------------------------------

def compute_dogleg(I1, I2, A1, A2):
    """
    Compute dog-leg angle (degrees) from two survey stations.
    """
    I1r = math.radians(I1)
    I2r = math.radians(I2)
    A1r = math.radians(A1)
    A2r = math.radians(A2)

    cos_dl = (math.cos(I2r - I1r) -
              math.sin(I1r) * math.sin(I2r) * (1 - math.cos(A2r - A1r)))
    # Clamp to avoid numerical issues
    cos_dl = max(-1.0, min(1.0, cos_dl))
    return math.degrees(math.acos(cos_dl))


def minimum_curvature(delta_MD, I1, I2, A1, A2):
    """
    Minimum curvature method.
    Returns: dTVD, dN, dE, dogleg_angle (degrees)
    """
    I1r = math.radians(I1)
    I2r = math.radians(I2)
    A1r = math.radians(A1)
    A2r = math.radians(A2)

    # Dog-leg angle
    dl = compute_dogleg(I1, I2, A1, A2)
    dl_rad = math.radians(dl)

    # Ratio factor
    if dl_rad == 0:
        rf = 1.0
    else:
        rf = (2.0 / dl_rad) * math.tan(dl_rad / 2.0)

    dTVD = (delta_MD / 2.0) * (math.cos(I1r) + math.cos(I2r)) * rf
    dN = (delta_MD / 2.0) * (math.sin(I1r) * math.cos(A1r) +
                             math.sin(I2r) * math.cos(A2r)) * rf
    dE = (delta_MD / 2.0) * (math.sin(I1r) * math.sin(A1r) +
                             math.sin(I2r) * math.sin(A2r)) * rf

    return dTVD, dN, dE, dl


def radius_of_curvature(delta_MD, I1, I2, A1, A2):
    """
    Radius of curvature method.
    Returns: dTVD, dN, dE, dogleg_angle (degrees)
    """
    I1r = math.radians(I1)
    I2r = math.radians(I2)
    A1r = math.radians(A1)
    A2r = math.radians(A2)

    dl = compute_dogleg(I1, I2, A1, A2)   # for reporting

    # If no change in inclination, use simple trig
    if I2r == I1r:
        dTVD = delta_MD * math.cos(I1r)
        dD = delta_MD * math.sin(I1r)      # departure in the horizontal plane
        dN = dD * math.cos(A1r)
        dE = dD * math.sin(A1r)
        return dTVD, dN, dE, dl

    # Vertical curvature
    delta_I = I2r - I1r
    R = delta_MD / delta_I
    dTVD = R * (math.sin(I2r) - math.sin(I1r))
    dD = R * (math.cos(I1r) - math.cos(I2r))

    # If no change in azimuth, use constant direction
    if A2r == A1r:
        dN = dD * math.cos(A1r)
        dE = dD * math.sin(A1r)
        return dTVD, dN, dE, dl

    # Horizontal curvature
    delta_A = A2r - A1r
    
    # Normalize delta_A to take the shortest path across North (360 degrees)
    while delta_A > math.pi:
        delta_A -= 2 * math.pi
    while delta_A < -math.pi:
        delta_A += 2 * math.pi
        
    R_h = dD / delta_A
    dN = R_h * (math.sin(A2r) - math.sin(A1r))
    dE = R_h * (math.cos(A1r) - math.cos(A2r))

    return dTVD, dN, dE, dl


# -------------------------------
# SIDEBAR
# -------------------------------
st.sidebar.header("⚙️ Settings")

method = st.sidebar.selectbox(
    "Calculation Method",
    ["Minimum Curvature", "Radius of Curvature", "Balanced Tangential"]
)

show_intermediate = st.sidebar.checkbox("Show intermediate calculations", value=False)

# -------------------------------
# INPUT TABLE
# -------------------------------
st.subheader("📥 Survey Data Input")
st.markdown("Enter measured depth (MD), inclination (0-180°), and azimuth (0-360°).")

# Default data from the document example
default_data = {
    "MD": [1200, 1400],
    "Inclination": [15, 19],
    "Azimuth": [320, 310]
}
data = st.data_editor(
    pd.DataFrame(default_data),
    num_rows="dynamic",
    column_config={
        "MD": st.column_config.NumberColumn("Measured Depth", min_value=0.0, step=1.0),
        "Inclination": st.column_config.NumberColumn("Inclination (°)", min_value=0.0, max_value=180.0, step=1.0),
        "Azimuth": st.column_config.NumberColumn("Azimuth (°)", min_value=0.0, max_value=360.0, step=1.0),
    }
)

# Reset index to avoid issues
data = data.reset_index(drop=True)

if len(data) < 2:
    st.warning("Enter at least 2 survey points")
    st.stop()

# Input validation
for i in range(len(data)):
    if data["MD"].iloc[i] < 0:
        st.error("MD cannot be negative")
        st.stop()
    if not (0 <= data["Inclination"].iloc[i] <= 180):
        st.error(f"Inclination at row {i+1} must be between 0 and 180")
        st.stop()
    if not (0 <= data["Azimuth"].iloc[i] <= 360):
        st.error(f"Azimuth at row {i+1} must be between 0 and 360")
        st.stop()

if not (data["MD"].diff().iloc[1:] > 0).all():
    st.error("MD must be strictly increasing")
    st.stop()

# -------------------------------
# CALCULATION
# -------------------------------
if st.button("🚀 Calculate Trajectory", type="primary"):

    # Prepare results lists
    TVD = [0.0]
    N = [0.0]
    E = [0.0]
    DLS_list = [0.0]      # dog-leg severity per 100 units (same as MD units)
    intervals = []        # to store intermediate data if requested

    for i in range(1, len(data)):
        delta_MD = data["MD"].iloc[i] - data["MD"].iloc[i-1]
        I1 = data["Inclination"].iloc[i-1]
        I2 = data["Inclination"].iloc[i]
        A1 = data["Azimuth"].iloc[i-1]
        A2 = data["Azimuth"].iloc[i]

        if method == "Minimum Curvature":
            dTVD, dN, dE, dl = minimum_curvature(delta_MD, I1, I2, A1, A2)
        elif method == "Radius of Curvature":
            dTVD, dN, dE, dl = radius_of_curvature(delta_MD, I1, I2, A1, A2)
        else:  # Balanced Tangential
            I1r, I2r = math.radians(I1), math.radians(I2)
            A1r, A2r = math.radians(A1), math.radians(A2)
            dTVD = (delta_MD / 2) * (math.cos(I1r) + math.cos(I2r))
            dN = (delta_MD / 2) * (math.sin(I1r) * math.cos(A1r) +
                                   math.sin(I2r) * math.cos(A2r))
            dE = (delta_MD / 2) * (math.sin(I1r) * math.sin(A1r) +
                                   math.sin(I2r) * math.sin(A2r))
            dl = compute_dogleg(I1, I2, A1, A2)

        dls = (dl / delta_MD) * 100.0   # per 100 units of MD (ft or m)
        DLS_list.append(dls)

        TVD.append(TVD[-1] + dTVD)
        N.append(N[-1] + dN)
        E.append(E[-1] + dE)

        if show_intermediate:
            intervals.append({
                "From MD": data["MD"].iloc[i-1],
                "To MD": data["MD"].iloc[i],
                "ΔMD": delta_MD,
                "I1": I1,
                "I2": I2,
                "A1": A1,
                "A2": A2,
                "Dogleg (°)": dl,
                "DLS (°/100)": dls,
                "ΔTVD": dTVD,
                "ΔNorthing": dN,
                "ΔEasting": dE
            })

    # -------------------------------
    # RESULTS DISPLAY
    # -------------------------------
    st.subheader("📊 Final Results")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Final TVD", f"{TVD[-1]:.2f}")
    col2.metric("Northing", f"{N[-1]:.2f}")
    col3.metric("Easting", f"{E[-1]:.2f}")
    
    # Compute final azimuth from last two points if available (approximate)
    if len(N) >= 2 and len(E) >= 2:
        final_az = math.degrees(math.atan2(E[-1]-E[-2], N[-1]-N[-2]))
        final_az = final_az if final_az >= 0 else 360 + final_az
        col4.metric("Final Azimuth", f"{final_az:.1f}°")
    else:
        col4.metric("Final Azimuth", "N/A")

    # Max DLS
    st.metric("Max Dog-leg Severity", f"{max(DLS_list):.2f} °/100")

    # -------------------------------
    # INTERMEDIATE TABLE
    # -------------------------------
    if show_intermediate and intervals:
        st.write("### 🔍 Interval Details")
        st.dataframe(pd.DataFrame(intervals))

    # -------------------------------
    # TRAJECTORY TABLE
    # -------------------------------
    result_df = pd.DataFrame({
        "MD": data["MD"],
        "TVD": TVD,
        "Northing": N,
        "Easting": E,
        "DLS (°/100)": DLS_list
    })
    st.write("### 📋 Trajectory Table")
    st.dataframe(result_df)

    # -------------------------------
    # EXPORT
    # -------------------------------
    csv = result_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="💾 Download Trajectory as CSV",
        data=csv,
        file_name="well_trajectory.csv",
        mime="text/csv",
    )

    # -------------------------------
    # PLOTS
    # -------------------------------
    st.subheader("📈 Well Path Visualization")

    # Top view (plan)
    fig1, ax1 = plt.subplots(figsize=(6, 5))
    ax1.plot(E, N, marker='o', linewidth=2)
    ax1.set_xlabel("Easting")
    ax1.set_ylabel("Northing")
    ax1.set_title("Top View")
    ax1.grid(True)
    ax1.axis('equal')   # maintain aspect ratio
    st.pyplot(fig1)

    # Vertical section (departure vs TVD)
    departure = [math.hypot(E[i], N[i]) for i in range(len(E))]
    fig2, ax2 = plt.subplots(figsize=(6, 5))
    ax2.plot(departure, TVD, marker='o', linewidth=2)
    ax2.invert_yaxis()
    ax2.set_xlabel("Departure (Horizontal Displacement)")
    ax2.set_ylabel("True Vertical Depth")
    ax2.set_title("Vertical Section")
    ax2.grid(True)
    st.pyplot(fig2)

    # DLS vs MD
    fig3, ax3 = plt.subplots(figsize=(8, 4))
    ax3.plot(data["MD"], DLS_list, marker='o', linewidth=2)
    ax3.set_xlabel("Measured Depth")
    ax3.set_ylabel("Dog-Leg Severity (°/100)")
    ax3.set_title("Dog-Leg Severity Profile")
    ax3.grid(True)
    st.pyplot(fig3)

    # -------------------------------
    # INTERACTIVE 3D VIEW (PLOTLY)
    # -------------------------------
    st.write("### 🧭 Interactive 3D Well Path")
    
    fig4 = go.Figure(data=[go.Scatter3d(
        x=E, 
        y=N, 
        z=TVD,
        mode='lines+markers',
        marker=dict(size=4, color='red'),
        line=dict(color='darkblue', width=4)
    )])

    fig4.update_layout(
        scene=dict(
            xaxis_title='Easting',
            yaxis_title='Northing',
            zaxis_title='TVD',
            zaxis_autorange='reversed', # Makes depth go DOWN
            aspectmode='data' # Keeps the scale proportional
        ),
        margin=dict(l=0, r=0, b=0, t=0),
        height=600
    )
    
    st.plotly_chart(fig4, use_container_width=True)

# -------------------------------
# FOOTER
# -------------------------------
st.markdown("---")
st.info(
    "**Methods:** Minimum Curvature (most accurate), Radius of Curvature (smooth arc), Balanced Tangential (simpler). "
    "Dog-leg severity is calculated per 100 units of measured depth (same units as input)."
)
