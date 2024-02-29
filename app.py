# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import plotly.express as px
from dash import Dash, html, dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import math
import datetime
from dplython import (DplyFrame, X, select, sift,arrange)

app = Dash(__name__, external_stylesheets = [dbc.themes.BOOTSTRAP])
server = app.server

pd.options.mode.chained_assignment = None  # default='warn'

th = pd.read_html("https://www.wahlrecht.de/umfragen/landtage/thueringen.htm")

df_new = th[1]
df_old = th[2]

df = pd.concat([df_new, df_old]).reset_index(drop = True)

# Alle Zeilen streichen, die nicht Umfragedaten darstellen (etwa Zeilen mit Spaltennamen)
df = df[df["CDU"].map(len) < 7]
df = df[df["Institut"] != "Institut"]


# Parteiwerte in Zahlenformat bringen # Sonstige lass ich erst einmal aus
Parteien = ["CDU","SPD","GRÜNE","FDP","LINKE","AfD"]

for col in Parteien:
    df[col] = df[col].str.replace(" %","").str.replace(",",".")
    df[col] = df[col].str.replace("?","").str.replace("310","31")
    df[col] = df[col].str.replace("–","nan").astype(float)
    


# Es gibt noch Duplikate. Datum dient als ID
df.drop_duplicates(inplace = True)


# Sonstige hinzufügen
df["Sonstige"] = 100 - np.nansum([df["CDU"],df["SPD"],df["GRÜNE"],df["LINKE"],df["FDP"],df["AfD"]],axis=0)


# Farben
party_colors = {'CDU':'black','SPD':'red','GRÜNE':'green','FDP':'gold','AfD':'#009ee0','LINKE':'purple','Sonstige':'lightgray'}
sitze_party_colors = {'SitzeFinalCDU':'black','SitzeFinalSPD':'red','SitzeFinalGRÜNE':'green','SitzeFinalFDP':'gold','SitzeFinalAfD':'#009ee0','SitzeFinalLINKE':'purple'}


# Datum ändern
df["Datum"] = df["Datum"].str.replace("Sept. 2004","01.09.2004").str.replace("Landtagswahl am ","") # 
df["Datum"] = pd.to_datetime(df["Datum"],format = "%d.%m.%Y")
df["Datum_str"] = df["Datum"].dt.strftime("%d.%m.%Y")
df = df.set_index('Datum')
df["Datum"] = df.index
df = df[::-1] # Reihenfolge ändern, damit für Balkendiagramme älteste Umfrage zuerst kommt


# eindeutige ID
df["Institut"] = df["Institut"].str.replace("- ","")
df["Umfrage"] = df["Datum_str"] + " " + df["Institut"]


# Sitze für alle # ist outdated sobald umrechungsverfahren fertig ist
for col in ["CDU", "SPD", "GRÜNE", "FDP", "LINKE", "AfD"]:
    df[f"Sitze{col}"] = df[col] * 88 / 100


#%% Hare/Niemeyer
# Erst werden die Sitze normal berechne (Prozent [eigentlich absolute Stimmen] * 88 / 100)
# Dann wird die Differenz zur Richtgröße 88 (hehe) berechnet.
# Die Parteien mit den größten Restwerten hinter dem Komma bekommen ein weiteres Mandat

# 5 Prozent-Hürde
for col in ["CDU", "SPD", "GRÜNE", "FDP", "LINKE", "AfD"]:
    df[f"hürde{col}"] = df[col].apply(lambda x: x if x > 4 else 0)
df["legaleProzent"] = df["hürdeCDU"]+df["hürdeSPD"]+df["hürdeGRÜNE"]+df["hürdeLINKE"]+df["hürdeAfD"]+df["hürdeFDP"]

# effektive Prozent (unter Berücksichtigung der 5 % Hürde)
for col in ["CDU", "SPD", "GRÜNE", "FDP", "LINKE", "AfD"]:
    df[f"effektiveProzent{col}"] =  df[f"hürde{col}"] / df["legaleProzent"] * 100
    
# Auf der Basis erste Runde Sitze berechnen
for col in ["CDU", "SPD", "GRÜNE", "FDP", "LINKE", "AfD"]:
    df[f"ersterDurchgang{col}"] = df[f"effektiveProzent{col}"] * 88 / 100
    
# Für Hare/Niemeyer: Float aufsplitten
for col in ["CDU", "SPD", "GRÜNE", "FDP", "LINKE", "AfD"]:
    df[f"integer{col}"] =  df[f"ersterDurchgang{col}"].apply(lambda x: math.modf(x)[1])
    df[f"decimal{col}"] =  df[f"ersterDurchgang{col}"].apply(lambda x: math.modf(x)[0])
    df[f"decimal{col}"].replace(0, np.nan, inplace=True)
    
# Summe der integer und Differenz zu 88
df["SummeInteger"] = df["integerCDU"]+df["integerSPD"]+df["integerGRÜNE"]+df["integerLINKE"]+df["integerAfD"]+df["integerFDP"]
df["Differenz"] = 88 - df["SummeInteger"]

# Dezimal-Rang der Parteien errechnen
ranks = df[["decimalCDU", "decimalSPD", "decimalGRÜNE", "decimalFDP", "decimalLINKE", "decimalAfD"]].rank(
    ascending=False, method='first', axis=1)
df = pd.concat([df, ranks.add_suffix('_rank')], axis=1)



# Zweite Runde Sitze. Die Differenz wird auf die Parteien verteilt. Der größte Dezimal bekommt plus 1, dann der zweite etc.
for col in ["CDU", "SPD", "GRÜNE", "FDP", "LINKE", "AfD"]:
    df[f"SitzeFinal{col}"] = np.where(
        df["Differenz"] >= df[f"decimal{col}_rank"],
        df[f"integer{col}"] + 1,
        df[f"integer{col}"]
    )

subset = df[["Differenz",
             "integerCDU", "decimalCDU","decimalCDU_rank","SitzeFinalCDU",
             "integerSPD","decimalSPD","decimalSPD_rank","SitzeFinalSPD",
             "integerGRÜNE","decimalGRÜNE","decimalGRÜNE_rank","SitzeFinalGRÜNE",
             "integerFDP","decimalFDP","decimalFDP_rank","SitzeFinalFDP",
             "integerLINKE","decimalLINKE","decimalLINKE_rank","SitzeFinalLINKE",
             "integerAfD", "decimalAfD", "decimalAfD_rank","SitzeFinalAfD"]] 

dfIndex = df.reset_index(drop=True)

## Graph Sitzverteilungen
Sitzverteilungen = px.bar(df,x = "Umfrage",
             y = ["SitzeFinalCDU","SitzeFinalSPD","SitzeFinalGRÜNE","SitzeFinalLINKE","SitzeFinalFDP","SitzeFinalAfD"],
             color_discrete_map = sitze_party_colors)
Sitzverteilungen.update_traces(marker_line_width = 0.05)
Sitzverteilungen.update_xaxes(showticklabels = False,linecolor = "gray",mirror = True)
Sitzverteilungen.update_yaxes(range = [0,88])
Sitzverteilungen.update_layout(bargap=0,
                               showlegend = False,
                               yaxis_title=None,
                               plot_bgcolor = "#f9f9f9",
                               paper_bgcolor = "#f9f9f9")

## Graph Sonntagsfrage
aktuelleUmfrage = df.tail(1)
aktuelleUmfrage = aktuelleUmfrage[["Datum_str","CDU","SPD","GRÜNE","LINKE","FDP","AfD","Sonstige"]]
aktuelleUmfrage = pd.melt(aktuelleUmfrage,
        id_vars = 'Datum_str',
        value_vars=["CDU", "SPD", "GRÜNE", "FDP", "LINKE", "AfD","Sonstige"])
aktuelleUmfrage.rename(columns = {"value":"Prozent",
                                  "variable":"Partei"},inplace = True)
aktuelleUmfrage = pd.concat([aktuelleUmfrage.iloc[:-1].sort_values(by="Prozent",ascending=False),
                             aktuelleUmfrage.iloc[-1:]])


Sonntagsfrage = px.bar(aktuelleUmfrage,
                       x = "Partei",
                       y = "Prozent",
                       color = "Partei",
                       color_discrete_map = party_colors,
                       text_auto=True,
                       template = "plotly_white")
Sonntagsfrage.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False,
                            hovertemplate=None,hoverinfo='skip',
                            marker_line_width = 0,
                            marker_line_color = "gray")
Sonntagsfrage.update_xaxes(visible = True)
Sonntagsfrage.update_layout(yaxis_title=None,
                            xaxis_title=None,
                            bargap = 0.3,
                            showlegend = False,
                            plot_bgcolor = "#f9f9f9",
                            paper_bgcolor = "#f9f9f9")



#%% DASHboard



app.layout = html.Div(
    [
         html.H1("Dashboard zur Landtagswahl in Thüringen 2024",
                 style = {"textAlign":"center"}),
         dbc.Row(
             [
                 dbc.Col(
                     [
                         html.H3("Wenn morgen Landtagswahl wäre..."),
                         html.Label(f"Die aktuellste Umfrage zur Landtagswahl vom {dfIndex.loc[len(dfIndex)-1,'Datum_str']} ({dfIndex.loc[len(dfIndex)-1,'Institut']})"),
                         dcc.Graph(figure = Sonntagsfrage)
                     ], width = 5,style = {"backgroundColor":"#f9f9f9",
                                           "boxShadow": "3px 3px 3px lightgrey",
                                           "margin": "5px",
                                           "paddingTop":"15px",
                                           "paddingLeft":"20px"}
                 ),
                 dbc.Col(
                     [
                         html.H3("Umfragewerte der Thüringer Parteien seit 1999"),
                         dbc.RadioItems(options = ["Linien","Balken"],
                                        value = "Linien",
                                        id = "graphType",
                                        inline = True),
                         dcc.Graph(id = "Umfragewerte")
                     ], width = 6,style = {"backgroundColor":"#f9f9f9",
                                           "boxShadow": "3px 3px 3px lightgrey",
                                           "margin": "5px",
                                           "paddingTop":"15px",
                                           "paddingLeft":"20px"}
                 )
             ],style = {"marginTop":"60px"}
         ),
         dbc.Row(
             [
                 dbc.Col(
                     [
                         html.H4("Sitzverteilungen anhand von Umfragewerten"),
                         html.Label("Umrechnung der Stimmen nach Hare/Niemeyer unter Berücksichtung der 5%-Hürde"),
                         dcc.Graph(figure = Sitzverteilungen)
                     ],width = 6,style = {"backgroundColor":"#f9f9f9",
                                           "boxShadow": "3px 3px 3px lightgrey",
                                           "margin": "5px",
                                           "paddingTop":"15px",
                                           "paddingLeft":"20px"}
                 ),
                 dbc.Col(
                     [
                         html.H4("Koalitionsrechner"),
                         dcc.Dropdown(id ="dropdownUmfrage",
                                      options = dfIndex["Umfrage"],
                                      value = dfIndex.loc[len(dfIndex)-1,'Umfrage'],
                                      style = {"marginRight":"50%"}),
                         dbc.Checklist(
                                options=[{"label": "CDU", "value": "SitzeFinalCDU"},
                                         {"label": "SPD", "value": "SitzeFinalSPD"},
                                         {"label": "LINKE", "value": "SitzeFinalLINKE"},
                                         {"label": "GRÜNE", "value": "SitzeFinalGRÜNE"},
                                         {"label": "FDP","value":"SitzeFinalFDP"},
                                         {"label": "AfD","value":"SitzeFinalAfD"}],
                                value=[],
                                id="switchesInput",
                                switch=True,
                                inline = True),
                         dcc.Graph(id="Koalitionsrechner")
                     ], width = 5,style = {"backgroundColor":"#f9f9f9",
                                           "boxShadow": "3px 3px 3px lightgrey",
                                           "margin": "5px",
                                           "paddingTop":"15px",
                                           "paddingLeft":"20px"}
                 ),                       
             ]
         )
     ],style = {"backgroundColor":"#f2f2f2",
                "border":"100px solid #f2f2f2"}
)

# Sonntagsfrage




# Umfragen: Unterschiedliche Darstellungen
@app.callback(
    Output("Umfragewerte","figure"),
    Input("graphType","value"))
def chooseGraphType(graphType):
    if graphType == "Linien":
        fig = px.line(df, x = "Datum",y = ["Sonstige","CDU","SPD","GRÜNE","LINKE","FDP","AfD"],
                      color_discrete_map = party_colors,
                      markers = True,
                      template = "simple_white")
        fig.update_yaxes(showgrid=True)
        fig.update_xaxes(range = [min(df["Datum"]) - datetime.timedelta(days=50),
                                  max(df["Datum"]) + datetime.timedelta(days=100)] )
        fig.update_layout(showlegend = False,
                          yaxis_title=None,
                          xaxis_title=None,
                          plot_bgcolor = "#f9f9f9",
                          paper_bgcolor = "#f9f9f9")
        return fig
    elif graphType == "Balken":
        fig = px.bar(df,x = "Umfrage",
                     y = ["CDU","SPD","GRÜNE","LINKE","FDP","AfD","Sonstige"],
                     color_discrete_map = party_colors)
        fig.update_xaxes(showticklabels = False,linecolor = "gray",mirror = True)
        fig.update_yaxes(range = [0,100])
        fig.update_layout(showlegend = False,
                          yaxis_title=None,
                          xaxis_title="Umfrage",
                          bargap = 0,
                          plot_bgcolor = "#f9f9f9",
                          paper_bgcolor = "#f9f9f9")
        fig.update_traces(marker_line_width = 0.05)
        return fig

# Koalitionsrechner 
@app.callback(
    Output("Koalitionsrechner","figure"),
    Input("switchesInput","value"),
    Input("dropdownUmfrage","value"))
def Koalitionsrechner(switchesInput,dropdownUmfrage):
     # Subset
     sub = df[switchesInput]
     sum_rows = sub.sum(axis=1)
     rest = 88 - sum_rows
     sub = pd.concat([df[["Umfrage"]],sub],axis = 1)
     sub["sum"] = sum_rows.astype("int")
     sub["Rest"] = rest
     # Plot
     subSingle = sub[sub["Umfrage"] == dropdownUmfrage].reset_index()
     fig = px.bar(subSingle,
                  x = "Umfrage",
                  y = switchesInput,
                  color_discrete_map=sitze_party_colors,
                  template = "plotly_white",
                  text_auto = True)
     fig.update_yaxes(range = [0,88],visible=True)
     fig.update_xaxes(showticklabels = False,visible=False,showgrid = False)
     fig.update_layout(showlegend=False,
                plot_bgcolor = "#f9f9f9",
                paper_bgcolor = "#f9f9f9",
                yaxis_title=None,
                xaxis_title=None,
                annotations = [dict(xref='paper',
                                                   yref='paper',
                                                   x=0.5, y=-0.25,
                                                   showarrow=False,
                                                   text =f'{subSingle.loc[0,"sum"]} von 45 benötigten Mandaten')])
     fig.add_hline(y=44,line_width=1.5, line_dash="dash", line_color="gray")
     return fig 
    

if __name__ == '__main__':
    app.run(debug=True,port=8052)


