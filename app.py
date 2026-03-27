import math
import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd

st.set_page_config(page_title="Directional Drilling Tool", layout="wide")

st.title("🛢️ Directional Drilling Calculator")
st.markdown("### Advanced Well Trajectory Analysis")

# -------------------------------
# SIDEBAR
# -------------------------------
st.sidebar.header("⚙️ Settings")

method = st.sidebar.selectbox(
    "Calculation Method",
    ["Minimum Curvature", "Radius of Curvature"]
)

# -------------------------------
# INPUT TABLE
# -------------------------------
st.subheader("📥 Survey Data Input")

data = st.data_editor(
    pd.DataFrame({
        "MD": [0, 100, 200],
        "Inclination": [0, 5, 10],
        "Azimuth": [0, 30, 45]
    }),
    num_rows="dynamic"
)

if len(data) < 2:
    st.warning("Enter at least 2 points")
    st.stop()

# -------------------------------
# METHODS
# -------------------------------
def minimum_curvature(delta_MD, I1, I2, A1, A2):
    I1, I2 = math.radians(I1), math.radians(I2)
    A1, A2 = math.radians(A1), math.radians(A2)

    DL = math.acos(
        math.cos(I2 - I1) -
        math.sin(I1)*math.sin(I2)*(1 - math.cos(A2 - A1))
    )

    RF = 1 if DL == 0 else (2 / DL) * math.tan(DL / 2)

    dN = (delta_MD/2)*(math.sin(I1)*math.cos(A1) + math.sin(I2)*math.cos(A2)) * RF
    dE = (delta_MD/2)*(math.sin(I1)*math.sin(A1) + math.sin(I2)*math.sin(A2)) * RF
    dTVD = (delta_MD/2)*(math.cos(I1) + math.cos(I2)) * RF

    return dTVD, dN, dE, math.degrees(DL)


def radius_of_curvature(delta_MD, I1, I2, A1, A2):
    I1, I2 = math.radians(I1), math.radians(I2)
    A1, A2 = math.radians(A1), math.radians(A2)

    if I2 == I1:
        R = 0
    else:
        R = delta_MD / (I2 - I1)

    dTVD = R * (math.sin(I2) - math.sin(I1))
    dD = R * (math.cos(I1) - math.cos(I2))

    A_avg = (A1 + A2) / 2
    dN = dD * math.cos(A_avg)
    dE = dD * math.sin(A_avg)

    return dTVD, dN, dE


# -------------------------------
# CALCULATE
# -------------------------------
if st.button("🚀 Calculate"):

    TVD, N, E = [0], [0], [0]
    doglegs = []
    DLS = []

    for i in range(1, len(data)):

        delta_MD = data["MD"][i] - data["MD"][i-1]

        if delta_MD <= 0:
            st.error("MD must increase")
            st.stop()

        I1 = data["Inclination"][i-1]
        I2 = data["Inclination"][i]
        A1 = data["Azimuth"][i-1]
        A2 = data["Azimuth"][i]

        if method == "Minimum Curvature":
            dTVD, dN, dE, DL = minimum_curvature(delta_MD, I1, I2, A1, A2)
            doglegs.append(DL)

            dls = (DL / delta_MD) * 100
            DLS.append(dls)

        else:
            dTVD, dN, dE = radius_of_curvature(delta_MD, I1, I2, A1, A2)
            DLS.append(0)

        TVD.append(TVD[-1] + dTVD)
        N.append(N[-1] + dN)
        E.append(E[-1] + dE)

    # -------------------------------
    # RESULTS
    # -------------------------------
    st.subheader("📊 Results")

    col1, col2, col3 = st.columns(3)
    col1.metric("Final TVD", f"{TVD[-1]:.2f}")
    col2.metric("Northing", f"{N[-1]:.2f}")
    col3.metric("Easting", f"{E[-1]:.2f}")

    if method == "Minimum Curvature":
        st.metric("Max DLS (°/100m)", f"{max(DLS):.2f}")

    # -------------------------------
    # TABLE
    # -------------------------------
    result_df = pd.DataFrame({
        "MD": data["MD"],
        "TVD": TVD,
        "Northing": N,
        "Easting": E,
        "DLS": [0] + DLS
    })

    st.write("### 📋 Trajectory Table")
    st.dataframe(result_df)

    # -------------------------------
    # PLOTS
    # -------------------------------
    st.subheader("📈 Plots")

    col1, col2 = st.columns(2)

    # Top View
    fig1 = plt.figure()
    plt.plot(E, N, marker='o')
    plt.xlabel("Easting")
    plt.ylabel("Northing")
    plt.title("Top View")
    col1.pyplot(fig1)

    # Vertical Section
    departure = [math.sqrt(E[i]**2 + N[i]**2) for i in range(len(E))]

    fig2 = plt.figure()
    plt.plot(departure, TVD, marker='o')
    plt.gca().invert_yaxis()
    plt.xlabel("Departure")
    plt.ylabel("TVD")
    plt.title("Vertical Section")
    col2.pyplot(fig2)

    # -------------------------------
    # DLS GRAPH
    # -------------------------------
    st.subheader("📉 Dog-Leg Severity")

    fig3 = plt.figure()
    plt.plot(data["MD"][1:], DLS, marker='o')
    plt.xlabel("Measured Depth")
    plt.ylabel("DLS (°/100m)")
    plt.title("Dog-Leg Severity vs MD")
    st.pyplot(fig3)

# -------------------------------
# INFO
# -------------------------------
st.markdown("---")
st.info("Includes Minimum Curvature, Radius of Curvature, Full Trajectory and DLS analysis.")
