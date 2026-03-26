import math
import streamlit as st
import matplotlib.pyplot as plt

st.title("Directional Drilling Calculator")

st.write("Enter survey data below:")

MD1 = st.number_input("MD1", value=0.0)
MD2 = st.number_input("MD2", value=100.0)

I1 = st.number_input("Inclination I1 (deg)", value=0.0)
I2 = st.number_input("Inclination I2 (deg)", value=10.0)

A1 = st.number_input("Azimuth A1 (deg)", value=0.0)
A2 = st.number_input("Azimuth A2 (deg)", value=30.0)

delta_MD = MD2 - MD1

def calculate(delta_MD, I1, I2, A1, A2):
    I1, I2 = math.radians(I1), math.radians(I2)
    A1, A2 = math.radians(A1), math.radians(A2)

    DL = math.acos(
        math.cos(I2 - I1) -
        math.sin(I1)*math.sin(I2)*(1 - math.cos(A2 - A1))
    )

    if DL == 0:
        RF = 1
    else:
        RF = (2 / DL) * math.tan(DL / 2)

    dN = (delta_MD/2)*(math.sin(I1)*math.cos(A1) + math.sin(I2)*math.cos(A2)) * RF
    dE = (delta_MD/2)*(math.sin(I1)*math.sin(A1) + math.sin(I2)*math.sin(A2)) * RF
    dTVD = (delta_MD/2)*(math.cos(I1) + math.cos(I2)) * RF

    return dTVD, dN, dE, math.degrees(DL)

if st.button("Calculate"):
    dTVD, dN, dE, DL = calculate(delta_MD, I1, I2, A1, A2)

    st.subheader("Results")
    st.write(f"TVD Change: {dTVD:.2f}")
    st.write(f"Northing Change: {dN:.2f}")
    st.write(f"Easting Change: {dE:.2f}")
    st.write(f"Dog-leg Angle: {DL:.2f}°")

    fig = plt.figure()
    plt.plot([0, dE], [0, dN], marker='o')
    plt.xlabel("Easting")
    plt.ylabel("Northing")
    plt.title("Well Path")

    st.pyplot(fig)