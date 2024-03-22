# -*- coding: utf-8 -*-
#%% Datenimport und Aufbereitung
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, html, dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import math
import datetime
import re


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
df = df.reset_index(drop = True)

# BSW hinzufügen
df["BSW"] = 0
for i in range(len(df)):
    if "BSW" in df.loc[i,"Sonstige"]:
        match = re.search(r'\d+', df.loc[i,"Sonstige"])
        df.loc[i,"BSW"] = match.group()

# Parteiwerte in Zahlenformat bringen # Sonstige lass ich erst einmal aus
Parteien = ["CDU","SPD","GRÜNE","FDP","LINKE","AfD","BSW"]

for col in Parteien:
    df[col] = df[col].str.replace(" %","").str.replace(",",".")
    df[col] = df[col].str.replace("?","").str.replace("310","31")
    df[col] = df[col].str.replace("–","nan").astype(float)
    
# Es gibt noch Duplikate. Datum dient als ID
df.drop_duplicates(inplace = True)

hintergrundFarbe = "#141b2d"
kachelFarbe = "#1f2940"
textFarbe = "#dfdfe2"
schattenFarbe = "#101417"
gridFarbe = "#5f6b87"



# Sonstige hinzufügen
df["Sonstige"] = 100 - np.nansum([df["CDU"],df["SPD"],df["GRÜNE"],df["LINKE"],df["FDP"],df["AfD"],df["BSW"]],axis=0)


# Farben
party_colors = {'CDU':'black','SPD':'#cb0100','GRÜNE':'green','FDP':'gold','AfD':'#009ee0',
                'LINKE':'#642d75','BSW':'#e97314','Sonstige':'lightgray','Dummy':'white'}
sitze_party_colors = {'SitzeFinalCDU':'black','SitzeFinalSPD':'#cb0100','SitzeFinalGRÜNE':'green',
                      'SitzeFinalFDP':'gold','SitzeFinalAfD':'#009ee0','SitzeFinalLINKE':'#642d75',
                      'SitzeFinalBSW':"#e97314",
                      'Dummy':kachelFarbe,'Rest':kachelFarbe}


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
#for col in Parteien:
#    df[f"Sitze{col}"] = df[col] * 88 / 100



# Hare/Niemeyer
# Erst werden die Sitze normal berechne (Prozent [eigentlich absolute Stimmen] * 88 / 100)
# Dann wird die Differenz zur Richtgröße 88 (hehe) berechnet.
# Die Parteien mit den größten Restwerten hinter dem Komma bekommen ein weiteres Mandat

# 5 Prozent-Hürde
for col in Parteien:
    df[f"hürde{col}"] = df[col].apply(lambda x: x if x > 4 else 0)
df["legaleProzent"] = df["hürdeCDU"]+df["hürdeSPD"]+df["hürdeGRÜNE"]+df["hürdeLINKE"]+df["hürdeAfD"]+df["hürdeFDP"]+df["hürdeBSW"]

# effektive Prozent (unter Berücksichtigung der 5 % Hürde)
for col in Parteien:
    df[f"effektiveProzent{col}"] =  df[f"hürde{col}"] / df["legaleProzent"] * 100
    
# Auf der Basis erste Runde Sitze berechnen
for col in Parteien:
    df[f"ersterDurchgang{col}"] = df[f"effektiveProzent{col}"] * 88 / 100
    
# Für Hare/Niemeyer: Float aufsplitten
for col in Parteien:
    df[f"integer{col}"] =  df[f"ersterDurchgang{col}"].apply(lambda x: math.modf(x)[1])
    df[f"decimal{col}"] =  df[f"ersterDurchgang{col}"].apply(lambda x: math.modf(x)[0])
    df[f"decimal{col}"].replace(0, np.nan, inplace=True)
    
# Summe der integer und Differenz zu 88
df["SummeInteger"] = df["integerCDU"]+df["integerSPD"]+df["integerGRÜNE"]+df["integerLINKE"]+df["integerAfD"]+df["integerFDP"]+df["integerBSW"]
df["Differenz"] = 88 - df["SummeInteger"]

# Dezimal-Rang der Parteien errechnen
ranks = df[["decimalCDU", "decimalSPD", "decimalGRÜNE", "decimalFDP", "decimalLINKE", "decimalAfD", "decimalBSW"]].rank(
    ascending=False, method='first', axis=1)
df = pd.concat([df, ranks.add_suffix('_rank')], axis=1)



# Zweite Runde Sitze. Die Differenz wird auf die Parteien verteilt. Der größte Dezimal bekommt plus 1, dann der zweite etc.
for col in Parteien:
    df[f"SitzeFinal{col}"] = np.where(
        df["Differenz"] >= df[f"decimal{col}_rank"],
        df[f"integer{col}"] + 1,
        df[f"integer{col}"]
    )

# =============================================================================
# subset = df[["Differenz",
#              "integerCDU", "decimalCDU","decimalCDU_rank","SitzeFinalCDU",
#              "integerSPD","decimalSPD","decimalSPD_rank","SitzeFinalSPD",
#              "integerGRÜNE","decimalGRÜNE","decimalGRÜNE_rank","SitzeFinalGRÜNE",
#              "integerFDP","decimalFDP","decimalFDP_rank","SitzeFinalFDP",
#              "integerLINKE","decimalLINKE","decimalLINKE_rank","SitzeFinalLINKE",
#              "integerAfD", "decimalAfD", "decimalAfD_rank","SitzeFinalAfD"]] 
# =============================================================================

dfIndex = df.reset_index(drop=True)



## Graph Sonntagsfrage
aktuelleUmfrage = df.tail(1)
aktuelleUmfrage = aktuelleUmfrage[["Datum_str","CDU","SPD","GRÜNE","LINKE","FDP","AfD","BSW","Sonstige"]]
aktuelleUmfrage = pd.melt(aktuelleUmfrage,
        id_vars = 'Datum_str',
        value_vars=["CDU", "SPD", "GRÜNE", "FDP", "LINKE", "AfD","BSW","Sonstige"])
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
                       template = "plotly_dark")
Sonntagsfrage.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False,
                            hovertemplate=None,hoverinfo='skip',
                            marker_line_width = 0,
                            marker_line_color = "gray")
Sonntagsfrage.update_xaxes(visible = True,fixedrange = True,
                           linecolor = gridFarbe)
Sonntagsfrage.update_yaxes(visible = True,fixedrange = True)
Sonntagsfrage.update_layout(yaxis_title=None,
                            xaxis_title=None,
                            yaxis_gridcolor=gridFarbe,
                            bargap = 0.3,
                            showlegend = False,
                            font_color = textFarbe,
                            plot_bgcolor = kachelFarbe,
                            paper_bgcolor = kachelFarbe)



# index for df
df["count"] = range(len(df))

# Tage bis zur Wahl berechnen
today = datetime.datetime.today()
wahltag = datetime.datetime.strptime('2024-09-01 08:00:00', '%Y-%m-%d %H:%M:%S')
tagenoch = wahltag - today
#%% DASHboard
app.layout = html.Div(
    [
         html.H1("Dashboard zur Landtagswahl in Thüringen 2024",
                 style = {"textAlign":"center",
                          "color":textFarbe}),
         html.H4(f"Die Wahllokale öffnen in {tagenoch.days} Tagen",
                 style = {"textAlign":"center",
                          "color":textFarbe}),
         dbc.Row(
             [
                 dbc.Col(
                     [
                         html.H3("Umfragewerte der Thüringer Parteien seit 1999",
                                 style ={"color":textFarbe}),
                         dbc.RadioItems(options = ["Umfragewerte","Hypothetische Sitzverteilungen"],
                                        value = "Umfragewerte",
                                        id = "graphType",
                                        inline = True,
                                        style ={"color":textFarbe}),
                         html.Caption(" "),
                         html.H6(id = "Zeitraum",
                                 style ={"color":textFarbe}),
                         dcc.RangeSlider(min = df["count"].min(),max = df["count"].max()+1,
                                         marks = {
                                             2:{'label':"Wahl 1999",'style':{'color':textFarbe}},
                                             31:{'label':"Wahl 2004",'style':{'color':textFarbe}},
                                             66:{'label':"Wahl 2009",'style':{'color':textFarbe}},
                                             85:{'label':"Wahl 2014",'style':{'color':textFarbe}},
                                             119:{'label':"Wahl 2019",'style':{'color':textFarbe}}}, 
                                         value = [df["count"].min(),df["count"].max()],
                                         id = "selectTime",
                                         allowCross = False,
                                       ),
                         dcc.Graph(id = "Umfragewerte")
                     ], width = 7,style = {"backgroundColor":kachelFarbe,
                                           "boxShadow": f"4px 4px 4px {schattenFarbe}",
                                           "margin": "5px",
                                           "paddingTop":"15px",
                                           "paddingLeft":"20px"}
                 ),
                dbc.Col(
                    [
                        html.H4("Koalitionsrechner",
                                style ={"color":textFarbe}),
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
                                        {"label": "AfD","value":"SitzeFinalAfD"},
                                        {"label": "BSW","value":"SitzeFinalBSW"}],
                               value=[],
                               id="switchesInput",
                               switch=True,
                               inline = True,
                               style ={"color":textFarbe}),
                        dcc.Graph(id="Koalitionsrechner")
                    ], width = 4,style = {"backgroundColor":kachelFarbe,
                                          "boxShadow": f"4px 4px 4px {schattenFarbe}",
                                          "margin": "5px",
                                          "marginLeft":"40px",
                                          "paddingTop":"15px",
                                          "paddingLeft":"20px"}
                )
             ],style = {"marginTop":"60px"}
         ),
         dbc.Row(
             [
                 dbc.Col(
                     [
                         html.H3("Wenn morgen Landtagswahl wäre",
                                 style ={"color":textFarbe}),
                         html.Label(f"Die aktuellste Umfrage zur Landtagswahl vom {dfIndex.loc[len(dfIndex)-1,'Datum_str']} ({dfIndex.loc[len(dfIndex)-1,'Institut']})",
                                    style ={"color":textFarbe}),
                         dcc.Graph(figure = Sonntagsfrage)
                     ], width = 6,style = {"backgroundColor":kachelFarbe,
                                           "boxShadow": f"4px 4px 4px {schattenFarbe}",
                                           "margin": "5px",
                                           "paddingTop":"15px",
                                           "paddingLeft":"20px"}
                 )                     
             ]
         ),
     html.H6("Quelle: https://www.wahlrecht.de/umfragen/landtage/thueringen.htm",style = {"marginTop":"60px",
                                                                                          "textAlign":"right",
                                                                                          "color":textFarbe})
     ],style = {"backgroundColor":hintergrundFarbe,
                "border":f"100px solid {hintergrundFarbe}"}
)

# Sonntagsfrage




# Umfragen: Unterschiedliche Darstellungen
@app.callback(
    Output("Umfragewerte","figure"),
    Input("graphType","value"),
    Input("selectTime","value"))
def chooseGraphType(graphType,selectTime):
    minTime = min(selectTime)
    maxTime = max(selectTime)+1
    subTime = df.query(f"count in {list(range(minTime,maxTime))}")
    if graphType == "Umfragewerte":
        fig = px.line(subTime, x = "Datum",y = ["Sonstige","CDU","SPD","GRÜNE","LINKE","FDP","AfD","BSW"],
                      color_discrete_map = party_colors,
                      markers = False,
                      template = "plotly_dark")
        fig.update_traces(line=dict(width=3))
        fig.update_yaxes(showgrid=True,
                         range = [0,55],
                         fixedrange = True)
        fig.update_xaxes(range = [min(subTime["Datum"]) - datetime.timedelta(days=50),
                                  max(subTime["Datum"]) + datetime.timedelta(days=100)],
                         color = textFarbe,
                         linecolor = gridFarbe,
                         fixedrange = True,)
        fig.update_layout(showlegend = True,
                          legend_title=None,
                          yaxis_title=None,
                          xaxis_title=None,
                          yaxis_gridcolor=gridFarbe,
                          font_color = textFarbe,
                          plot_bgcolor = kachelFarbe,
                          paper_bgcolor = kachelFarbe)
        return fig
    elif graphType == "Hypothetische Sitzverteilungen":
        ## Graph Sitzverteilungen
        Sitzverteilungen = px.bar(subTime,x = "Umfrage",
                     y = ["SitzeFinalCDU","SitzeFinalSPD","SitzeFinalGRÜNE","SitzeFinalLINKE","SitzeFinalFDP","SitzeFinalAfD","SitzeFinalBSW"],
                     color_discrete_map = sitze_party_colors)
        Sitzverteilungen.update_traces(marker_line_width = 0)
        Sitzverteilungen.update_xaxes(showticklabels = False,linecolor = kachelFarbe,
                                      mirror = True,fixedrange = True)
        Sitzverteilungen.update_yaxes(fixedrange = True)
        Sitzverteilungen.update_layout(yaxis_range = [0,88],
                                       bargap=0,
                                       showlegend = False,
                                       yaxis_title=None,
                                       font_color = textFarbe,
                                       plot_bgcolor = kachelFarbe,
                                       paper_bgcolor = kachelFarbe)
        return Sitzverteilungen

# Zeitraum angeben für Umfragen
@app.callback(
    Output("Zeitraum","children"),
    Input("selectTime","value"))
def chooseTimeframe(selectTime):
    minTime = min(selectTime)
    maxTime = max(selectTime)+1
    subTime = df.query(f"count in {list(range(minTime,maxTime))}")
    datemin = subTime.index.min().strftime('%d.%m.%Y')
    datemax = subTime.index.max().strftime('%d.%m.%Y')
    text = (f"Zeitraum: {datemin} - {datemax}")
    return text

sitze_party_colors_text = {'SitzeFinalCDU':textFarbe,'SitzeFinalSPD':textFarbe,'SitzeFinalGRÜNE':textFarbe,
                      'SitzeFinalFDP':textFarbe,'SitzeFinalAfD':textFarbe,'SitzeFinalLINKE':textFarbe,
                      'SitzeFinalBSW':textFarbe,
                      'Dummy':kachelFarbe,'Rest':kachelFarbe}    
# Koalitionsrechner 
@app.callback(
    Output("Koalitionsrechner","figure"),
    Input("switchesInput","value"),
    Input("dropdownUmfrage","value"))
def Koalitionsrechner(switchesInput,dropdownUmfrage):
     # Subset
     sub = df[switchesInput]
     sub["Dummy"] = 88
     sum_rows = sub.sum(axis=1)
     rest = 176 - sum_rows
     sub["Rest"] = rest
     sub = pd.concat([df[["Umfrage"]],sub],axis = 1)

             

     # Plot
     subSingle = sub[sub["Umfrage"] == dropdownUmfrage].reset_index()
     summe = 0
     for col in switchesInput:
         summe += subSingle.loc[0,col]

     subSingle = subSingle = pd.melt(subSingle,
                         id_vars = ["Umfrage"],
                         value_vars = switchesInput.append("Dummy"))
     subSingle.rename(columns = {"value":"Prozent",
                                 "variable":"Partei"},inplace = True)
     
     cols = subSingle['Partei'].map(sitze_party_colors)
     cols_text = subSingle['Partei'].map(sitze_party_colors_text)
     fig = go.Figure()
     fig.add_trace(
                   go.Pie(
                          labels = subSingle["Partei"],
                          values = subSingle["Prozent"],
                          hole = 0.3,
                          direction="clockwise",
                          rotation=270,
                          marker = dict(colors = cols,
                                        line=dict(color=kachelFarbe, width=3)),
                          sort = False,
                          textinfo = "value",
                          textfont= dict(color = kachelFarbe,size = 24 ) ,
                          hoverinfo="none",
                          )
                   )     
     fig.update_layout(showlegend=False,
                       plot_bgcolor = kachelFarbe,
                       paper_bgcolor = kachelFarbe,
                       font_color = textFarbe,
                       autosize = True,
                       annotations =[dict(text=f'{int(summe)} von 88 Mandaten.<br>Einfache Mehrheit bei 45 Mandaten.', x=0.5, y=0.4, font_size=20, showarrow=False)])
     return fig 
    

if __name__ == '__main__':
    app.run(debug=True,port=8052)



# %%
