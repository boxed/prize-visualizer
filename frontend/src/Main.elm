module Main exposing (main)

import Browser
import Dict exposing (Dict)
import Html exposing (Html, button, div, h1, h2, label, option, p, select, span, text)
import Html.Attributes as A
import Html.Events as E
import Http
import Json.Decode as D
import Svg exposing (Svg)
import Svg.Attributes as SA
import Svg.Events as SE



-- MODEL


type alias Prize =
    { id : String
    , name : String
    , kind : String
    , year : Int
    , category : Maybe String
    , gender : Maybe String
    , birthCountry : Maybe String
    , currentCountry : Maybe String
    , birthYear : Maybe Int
    , religions : List String
    , ethnicGroups : List String
    , wikipediaSlug : Maybe String
    , prize : String
    }


type alias Population =
    { country : String
    , populationMillions : Float
    }


type Tab
    = TopCountries
    | PerCapita
    | OverTime
    | GenderOverTime
    | ByCategory
    | ByReligion
    | ByEthnicGroup


type alias Model =
    { prizes : List Prize
    , populations : Dict String Float
    , status : Status
    , tab : Tab
    , categoryFilter : Maybe String
    , prizeFilter : Maybe String
    , minYear : Int
    , maxYear : Int
    , selection : Selection
    }


type Selection
    = NoSel
    | SelCountry String
    | SelCategory String
    | SelReligion String
    | SelEthnicGroup String
    | SelMissingReligion
    | SelMissingEthnicGroup
    | SelDecade Int
    | SelYear Int


unknownLabel : String
unknownLabel =
    "(unknown / not in Wikidata)"


selectionLabel : Selection -> String
selectionLabel sel =
    case sel of
        NoSel ->
            ""

        SelCountry s ->
            "country: " ++ s

        SelCategory s ->
            "category: " ++ s

        SelReligion s ->
            "religion: " ++ s

        SelEthnicGroup s ->
            "ethnic group: " ++ s

        SelMissingReligion ->
            "religion: " ++ unknownLabel

        SelMissingEthnicGroup ->
            "ethnic group: " ++ unknownLabel

        SelDecade y ->
            "decade: " ++ String.fromInt y ++ "s"

        SelYear y ->
            "year: " ++ String.fromInt y


prizeMatchesSelection : Selection -> Prize -> Bool
prizeMatchesSelection sel p =
    case sel of
        NoSel ->
            False

        SelCountry s ->
            p.currentCountry == Just s

        SelCategory s ->
            p.category == Just s

        SelReligion s ->
            List.member s p.religions

        SelEthnicGroup s ->
            List.member s p.ethnicGroups

        SelMissingReligion ->
            List.isEmpty p.religions

        SelMissingEthnicGroup ->
            List.isEmpty p.ethnicGroups

        SelDecade y ->
            p.year >= y && p.year < y + 10

        SelYear y ->
            p.year == y


type Status
    = Loading
    | Ready
    | Failed String


init : () -> ( Model, Cmd Msg )
init _ =
    ( { prizes = []
      , populations = Dict.empty
      , status = Loading
      , tab = TopCountries
      , categoryFilter = Nothing
      , prizeFilter = Nothing
      , minYear = 1901
      , maxYear = 2026
      , selection = NoSel
      }
    , Cmd.batch [ fetchPrizes, fetchPopulation ]
    )



-- HTTP


fetchPrizes : Cmd Msg
fetchPrizes =
    Http.get
        { url = "/data/processed/prizes.json"
        , expect = Http.expectJson GotPrizes (D.list prizeDecoder)
        }


fetchPopulation : Cmd Msg
fetchPopulation =
    Http.get
        { url = "/data/processed/population.json"
        , expect = Http.expectJson GotPopulation (D.list populationDecoder)
        }


prizeDecoder : D.Decoder Prize
prizeDecoder =
    let
        partial =
            D.map8
                (\a b c d e f g h by rels eths slug pz -> Prize a b c d e f g h by rels eths slug pz)
                (D.field "id" D.string)
                (D.oneOf [ D.field "name" D.string, D.succeed "—" ])
                (D.field "kind" D.string)
                (D.field "year" D.int)
                (D.field "category" (D.nullable D.string))
                (D.field "gender" (D.nullable D.string))
                (D.field "birthCountry" (D.nullable D.string))
                (D.field "currentCountry" (D.nullable D.string))
    in
    D.map5 (\f by rels eths slug -> f by rels eths slug)
        partial
        (D.field "birthYear" (D.nullable D.int))
        (D.oneOf [ D.field "religions" (D.list D.string), D.succeed [] ])
        (D.oneOf [ D.field "ethnicGroups" (D.list D.string), D.succeed [] ])
        (D.oneOf [ D.field "wikipediaSlug" (D.nullable D.string), D.succeed Nothing ])
        |> D.andThen
            (\partialFn ->
                D.map (\pz -> partialFn pz)
                    (D.oneOf [ D.field "prize" D.string, D.succeed "Nobel Prize" ])
            )


populationDecoder : D.Decoder Population
populationDecoder =
    D.map2 Population
        (D.field "country" D.string)
        (D.field "populationMillions" D.float)



-- UPDATE


type Msg
    = GotPrizes (Result Http.Error (List Prize))
    | GotPopulation (Result Http.Error (List Population))
    | SetTab Tab
    | SetCategory String
    | SetPrize String
    | SetMinYear String
    | SetMaxYear String
    | Select Selection
    | ClearSelection


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        GotPrizes (Ok ps) ->
            ( { model | prizes = ps, status = readyIf (not (List.isEmpty ps) && not (Dict.isEmpty model.populations) || List.isEmpty ps) model.status }, Cmd.none )
                |> markReady

        GotPrizes (Err e) ->
            ( { model | status = Failed (httpErrToString "prizes" e) }, Cmd.none )

        GotPopulation (Ok ps) ->
            ( { model | populations = Dict.fromList (List.map (\p -> ( p.country, p.populationMillions )) ps) }, Cmd.none )
                |> markReady

        GotPopulation (Err e) ->
            ( { model | status = Failed (httpErrToString "population" e) }, Cmd.none )

        SetTab t ->
            ( { model | tab = t, selection = NoSel }, Cmd.none )

        Select sel ->
            ( { model | selection = sel }, Cmd.none )

        ClearSelection ->
            ( { model | selection = NoSel }, Cmd.none )

        SetCategory s ->
            ( { model
                | categoryFilter =
                    if s == "" then
                        Nothing

                    else
                        Just s
              }
            , Cmd.none
            )

        SetPrize s ->
            ( { model
                | prizeFilter =
                    if s == "" then
                        Nothing

                    else
                        Just s
                , selection = NoSel
              }
            , Cmd.none
            )

        SetMinYear s ->
            ( { model | minYear = String.toInt s |> Maybe.withDefault model.minYear }, Cmd.none )

        SetMaxYear s ->
            ( { model | maxYear = String.toInt s |> Maybe.withDefault model.maxYear }, Cmd.none )


markReady : ( Model, Cmd Msg ) -> ( Model, Cmd Msg )
markReady ( m, c ) =
    if not (List.isEmpty m.prizes) && not (Dict.isEmpty m.populations) then
        ( { m | status = Ready }, c )

    else
        ( m, c )


readyIf : Bool -> Status -> Status
readyIf b s =
    if b then
        Ready

    else
        s


httpErrToString : String -> Http.Error -> String
httpErrToString src err =
    let
        base =
            "failed to load " ++ src ++ ": "
    in
    case err of
        Http.BadUrl u ->
            base ++ "bad url " ++ u

        Http.Timeout ->
            base ++ "timeout"

        Http.NetworkError ->
            base ++ "network error"

        Http.BadStatus s ->
            base ++ "status " ++ String.fromInt s

        Http.BadBody b ->
            base ++ "bad body " ++ b



-- FILTERING / AGGREGATION


filtered : Model -> List Prize
filtered model =
    model.prizes
        |> List.filter (\p -> p.year >= model.minYear && p.year <= model.maxYear)
        |> List.filter
            (\p ->
                case model.categoryFilter of
                    Nothing ->
                        True

                    Just c ->
                        p.category == Just c
            )
        |> List.filter
            (\p ->
                case model.prizeFilter of
                    Nothing ->
                        True

                    Just c ->
                        p.prize == c
            )


uniqueSorted : (a -> String) -> List a -> List String
uniqueSorted getter xs =
    xs
        |> List.map getter
        |> List.foldl
            (\v d -> Dict.insert v () d)
            Dict.empty
        |> Dict.keys


countBy : (Prize -> Maybe String) -> List Prize -> List ( String, Int )
countBy keyFn prizes =
    prizes
        |> List.filterMap (\p -> keyFn p |> Maybe.map (\k -> ( k, 1 )))
        |> List.foldl
            (\( k, _ ) d ->
                Dict.update k (Maybe.map ((+) 1) >> Maybe.withDefault 1 >> Just) d
            )
            Dict.empty
        |> Dict.toList
        |> List.sortBy (\( _, n ) -> -n)


countByYear : List Prize -> List ( Int, Int )
countByYear prizes =
    prizes
        |> List.foldl
            (\p d ->
                Dict.update p.year (Maybe.map ((+) 1) >> Maybe.withDefault 1 >> Just) d
            )
            Dict.empty
        |> Dict.toList
        |> List.sortBy Tuple.first


genderByYear : List Prize -> List ( Int, ( Int, Int, Int ) )
genderByYear prizes =
    prizes
        |> List.foldl
            (\p d ->
                let
                    bump ( m, f, o ) =
                        case p.gender of
                            Just "male" ->
                                ( m + 1, f, o )

                            Just "female" ->
                                ( m, f + 1, o )

                            _ ->
                                ( m, f, o + 1 )
                in
                Dict.update p.year (Maybe.withDefault ( 0, 0, 0 ) >> bump >> Just) d
            )
            Dict.empty
        |> Dict.toList
        |> List.sortBy Tuple.first



-- VIEW


view : Model -> Html Msg
view model =
    div [ A.class "wrap" ]
        [ Html.node "style" [] [ text styles ]
        , h1 [] [ text "Prize Visualizer" ]
        , p [ A.class "muted" ] [ text "Nobel Prizes (1901–present, from the official Nobel API) plus other high-prestige scientific prizes (Fields Medal, Turing Award, Abel Prize, Wolf, Crafoord, Breakthrough, Kavli, Copley, Lasker — from Wikidata). Country = laureate's birthplace, mapped to modern equivalent. Population ≈ 2023." ]
        , case model.status of
            Loading ->
                div [ A.class "loading" ] [ text "loading…" ]

            Failed e ->
                div [ A.class "error" ] [ text e ]

            Ready ->
                viewReady model
        ]


viewReady : Model -> Html Msg
viewReady model =
    let
        ps =
            filtered model

        hidden =
            hiddenTabs ps

        effectiveTab =
            if List.member model.tab hidden then
                TopCountries

            else
                model.tab
    in
    div []
        [ viewControls model
        , viewTabs model hidden
        , viewSummary ps
        , case effectiveTab of
            TopCountries ->
                viewTopCountries ps

            PerCapita ->
                viewPerCapita model.populations ps

            OverTime ->
                viewOverTime ps

            GenderOverTime ->
                viewGenderOverTime model ps

            ByCategory ->
                viewByCategory ps

            ByReligion ->
                viewByMultiTag "religion" .religions ps

            ByEthnicGroup ->
                viewByMultiTag "ethnic group" .ethnicGroups ps
        , viewDrilldown model ps
        ]


hiddenTabs : List Prize -> List Tab
hiddenTabs ps =
    let
        uniqueCount getter =
            ps
                |> List.filterMap getter
                |> List.foldl (\v d -> Dict.insert v () d) Dict.empty
                |> Dict.size
    in
    List.concat
        [ if uniqueCount .category < 2 then
            [ ByCategory ]

          else
            []
        ]


viewDrilldown : Model -> List Prize -> Html Msg
viewDrilldown model filteredPrizes =
    case model.selection of
        NoSel ->
            text ""

        sel ->
            let
                matching =
                    List.filter (prizeMatchesSelection sel) filteredPrizes
                        |> List.sortBy (\p -> ( -p.year, p.name ))

                yearCounts =
                    countByYear matching
            in
            div [ A.class "drilldown" ]
                [ div [ A.class "drilldown-header" ]
                    [ span [ A.class "drilldown-title" ]
                        [ text
                            (String.fromInt (List.length matching)
                                ++ " laureates — "
                                ++ selectionLabel sel
                            )
                        ]
                    , button [ A.class "clear-btn", E.onClick ClearSelection ] [ text "× clear" ]
                    ]
                , if List.isEmpty matching then
                    p [ A.class "muted" ] [ text "No matching laureates." ]

                  else
                    div []
                        [ yearlyBarChart model.minYear model.maxYear yearCounts
                        , Html.ul [ A.class "laureate-list" ] (List.map viewLaureate matching)
                        ]
                ]


yearlyBarChart : Int -> Int -> List ( Int, Int ) -> Html Msg
yearlyBarChart minY maxY rows =
    let
        w =
            900

        h =
            140

        padL =
            32

        padR =
            12

        padT =
            8

        padB =
            22

        years =
            max 1 (maxY - minY + 1)

        barW =
            toFloat (w - padL - padR) / toFloat years

        maxC =
            rows |> List.map Tuple.second |> List.maximum |> Maybe.withDefault 1

        yScale c =
            toFloat (h - padB) - toFloat c / toFloat maxC * toFloat (h - padT - padB)

        xPos year =
            toFloat padL + toFloat (year - minY) * barW

        bar ( y, c ) =
            Svg.g [ SE.onClick (Select (SelYear y)), SA.class "barrow clickable" ]
                [ Svg.rect
                    [ SA.x (String.fromFloat (xPos y))
                    , SA.y (String.fromInt padT)
                    , SA.width (String.fromFloat (max 1 barW))
                    , SA.height (String.fromFloat (toFloat (h - padB) - toFloat padT))
                    , SA.class "barhit"
                    ]
                    []
                , Svg.rect
                    [ SA.x (String.fromFloat (xPos y))
                    , SA.y (String.fromFloat (yScale c))
                    , SA.width (String.fromFloat (max 1 (barW - 1)))
                    , SA.height (String.fromFloat (toFloat (h - padB) - yScale c))
                    , SA.class "bar"
                    ]
                    []
                , Svg.title [] [ Svg.text (String.fromInt y ++ ": " ++ String.fromInt c) ]
                ]

        xLabels =
            tickIntegers minY maxY 8
                |> List.map
                    (\y ->
                        Svg.text_
                            [ SA.x (String.fromFloat (xPos y))
                            , SA.y (String.fromInt (h - padB + 14))
                            , SA.textAnchor "middle"
                            , SA.class "axis"
                            ]
                            [ Svg.text (String.fromInt y) ]
                    )

        yLabel =
            Svg.text_
                [ SA.x (String.fromInt (padL - 4))
                , SA.y (String.fromInt (padT + 8))
                , SA.textAnchor "end"
                , SA.class "axis"
                ]
                [ Svg.text ("max " ++ String.fromInt maxC) ]
    in
    Svg.svg
        [ SA.viewBox ("0 0 " ++ String.fromInt w ++ " " ++ String.fromInt h)
        , SA.width "100%"
        , SA.height (String.fromInt h)
        , SA.class "yearly-chart"
        ]
        (yLabel :: List.map bar rows ++ xLabels)


viewLaureate : Prize -> Html Msg
viewLaureate p =
    let
        country =
            p.currentCountry |> Maybe.withDefault "—"

        cat =
            p.category |> Maybe.withDefault ""

        meta =
            [ String.fromInt p.year, p.prize, cat, country ]
                |> List.filter (\s -> s /= "")
                |> String.join " · "

        extra =
            (if List.isEmpty p.religions then
                []

             else
                [ "religion: " ++ String.join ", " p.religions ]
            )
                ++ (if List.isEmpty p.ethnicGroups then
                        []

                    else
                        [ "ethnicity: " ++ String.join ", " p.ethnicGroups ]
                   )
                |> String.join "; "

        wikiLink =
            case p.wikipediaSlug of
                Just slug ->
                    [ Html.a
                        [ A.href ("https://en.wikipedia.org/wiki/" ++ slug)
                        , A.target "_blank"
                        , A.class "wiki-link"
                        ]
                        [ text "wiki" ]
                    ]

                Nothing ->
                    []
    in
    Html.li [ A.class "laureate" ]
        ([ span [ A.class "laureate-name" ] [ text p.name ]
         , span [ A.class "laureate-meta" ] [ text (" — " ++ meta) ]
         ]
            ++ (if extra == "" then
                    []

                else
                    [ span [ A.class "laureate-extra" ] [ text (" (" ++ extra ++ ")") ] ]
               )
            ++ wikiLink
        )


viewControls : Model -> Html Msg
viewControls model =
    let
        prizes =
            uniqueSorted .prize model.prizes

        cats =
            model.prizes
                |> List.filterMap .category
                |> List.foldl (\v d -> Dict.insert v () d) Dict.empty
                |> Dict.keys
    in
    div [ A.class "controls" ]
        [ label []
            [ text "Prize: "
            , select [ E.onInput SetPrize ]
                (option [ A.value "" ] [ text "All prizes" ]
                    :: List.map
                        (\c -> option [ A.value c, A.selected (model.prizeFilter == Just c) ] [ text c ])
                        prizes
                )
            ]
        , label []
            [ text " Category: "
            , select [ E.onInput SetCategory ]
                (option [ A.value "" ] [ text "All categories" ]
                    :: List.map
                        (\c -> option [ A.value c, A.selected (model.categoryFilter == Just c) ] [ text c ])
                        cats
                )
            ]
        , label []
            [ text " From year: "
            , Html.input
                [ A.type_ "number"
                , A.value (String.fromInt model.minYear)
                , A.min "1700"
                , A.max "2026"
                , E.onInput SetMinYear
                ]
                []
            ]
        , label []
            [ text " To year: "
            , Html.input
                [ A.type_ "number"
                , A.value (String.fromInt model.maxYear)
                , A.min "1700"
                , A.max "2026"
                , E.onInput SetMaxYear
                ]
                []
            ]
        ]


viewTabs : Model -> List Tab -> Html Msg
viewTabs model hidden =
    let
        all =
            [ ( TopCountries, "By country" )
            , ( PerCapita, "Per capita" )
            , ( OverTime, "Over time" )
            , ( GenderOverTime, "Gender over time" )
            , ( ByCategory, "By category" )
            , ( ByReligion, "By religion" )
            , ( ByEthnicGroup, "By ethnicity" )
            ]
    in
    div [ A.class "tabs" ]
        (all
            |> List.filter (\( t, _ ) -> not (List.member t hidden))
            |> List.map (\( t, lbl ) -> tabBtn model t lbl)
        )


tabBtn : Model -> Tab -> String -> Html Msg
tabBtn model t lbl =
    button
        [ E.onClick (SetTab t)
        , A.classList [ ( "tab", True ), ( "active", model.tab == t ) ]
        ]
        [ text lbl ]


viewSummary : List Prize -> Html Msg
viewSummary ps =
    div [ A.class "summary" ]
        [ span [] [ text (String.fromInt (List.length ps) ++ " prizes in current selection") ] ]


viewTopCountries : List Prize -> Html Msg
viewTopCountries ps =
    let
        rows =
            countBy .currentCountry ps |> List.take 25
    in
    div []
        [ h2 [] [ text "Top countries (absolute)" ]
        , barChart (Just (\( c, _ ) -> Select (SelCountry c))) rows (\( _, n ) -> toFloat n) (\( c, n ) -> c ++ " — " ++ String.fromInt n)
        ]


viewPerCapita : Dict String Float -> List Prize -> Html Msg
viewPerCapita populations ps =
    let
        counts =
            countBy .currentCountry ps

        rows =
            counts
                |> List.filterMap
                    (\( c, n ) ->
                        Dict.get c populations
                            |> Maybe.map (\pop -> ( c, ( n, toFloat n / pop ) ))
                    )
                |> List.filter (\( _, ( n, _ ) ) -> n >= 2)
                |> List.sortBy (\( _, ( _, perM ) ) -> -perM)
                |> List.take 30
    in
    div []
        [ h2 [] [ text "Prizes per million people" ]
        , p [ A.class "muted" ] [ text "Countries with fewer than 2 prizes excluded to keep the chart legible." ]
        , barChart
            (Just (\( c, _ ) -> Select (SelCountry c)))
            rows
            (\( _, ( _, perM ) ) -> perM)
            (\( c, ( n, perM ) ) ->
                c
                    ++ " — "
                    ++ formatFloat 2 perM
                    ++ " / million ("
                    ++ String.fromInt n
                    ++ " total)"
            )
        ]


viewOverTime : List Prize -> Html Msg
viewOverTime ps =
    let
        rows =
            countByYear ps
    in
    div []
        [ h2 [] [ text "Prizes per year" ]
        , lineChart rows
        ]


viewGenderOverTime : Model -> List Prize -> Html Msg
viewGenderOverTime model ps =
    let
        rows =
            genderByYear ps
    in
    div []
        [ h2 [] [ text "Gender split per year" ]
        , p [ A.class "muted" ] [ text "Stacked per year. Organizations and unknowns shown in grey. Click any bar to drill in." ]
        , stackedYearChart model.minYear model.maxYear rows
        ]


viewByCategory : List Prize -> Html Msg
viewByCategory ps =
    let
        rows =
            countBy .category ps
    in
    div []
        [ h2 [] [ text "Prizes by category" ]
        , barChart (Just (\( c, _ ) -> Select (SelCategory c))) rows (\( _, n ) -> toFloat n) (\( c, n ) -> c ++ " — " ++ String.fromInt n)
        ]


viewByMultiTag : String -> (Prize -> List String) -> List Prize -> Html Msg
viewByMultiTag label getter ps =
    let
        total =
            List.length ps

        ( tagged, untagged ) =
            List.partition (\p -> not (List.isEmpty (getter p))) ps

        unknownCount =
            List.length untagged

        knownRows =
            tagged
                |> List.concatMap getter
                |> List.foldl
                    (\k d -> Dict.update k (Maybe.map ((+) 1) >> Maybe.withDefault 1 >> Just) d)
                    Dict.empty
                |> Dict.toList
                |> List.sortBy (\( _, n ) -> -n)
                |> List.take 25

        rows =
            if unknownCount > 0 then
                ( unknownLabel, unknownCount ) :: knownRows

            else
                knownRows

        coverage =
            if total == 0 then
                "0%"

            else
                formatFloat 1 (toFloat (List.length tagged) * 100 / toFloat total) ++ "%"

        isMissingDim s =
            s == unknownLabel

        onClickFn ( c, _ ) =
            Select
                (if isMissingDim c then
                    if label == "religion" then
                        SelMissingReligion

                    else
                        SelMissingEthnicGroup

                 else if label == "religion" then
                    SelReligion c

                 else
                    SelEthnicGroup c
                )

        labelFn ( c, n ) =
            c ++ " — " ++ String.fromInt n
    in
    div []
        [ h2 [] [ text ("Prizes by " ++ label ++ " (Wikidata)") ]
        , div [ A.class "warning" ]
            [ text
                ("Sourced from Wikidata "
                    ++ (if label == "religion" then
                            "P140"

                        else
                            "P172"
                       )
                    ++ ". Coverage in current selection: "
                    ++ String.fromInt (List.length tagged)
                    ++ " of "
                    ++ String.fromInt total
                    ++ " prizes ("
                    ++ coverage
                    ++ "). The rest are bucketed as “unknown” — Wikidata simply has no value recorded. P172 (ethnic group) is also typically only used for minority/diaspora identities, so majority national identities (e.g. Swedish, French) generally appear as unknown rather than tagged."
                )
            ]
        , if List.isEmpty rows then
            p [ A.class "muted" ] [ text "No prizes in current selection." ]

          else
            barChartTagged onClickFn rows labelFn isMissingDim
        ]


barChartTagged :
    (( String, Int ) -> Msg)
    -> List ( String, Int )
    -> (( String, Int ) -> String)
    -> (String -> Bool)
    -> Html Msg
barChartTagged onClickFn rows labelFn isUnknown =
    let
        n =
            List.length rows

        rowH =
            26

        labelW =
            340

        chartW =
            520

        height =
            n * rowH + 20

        maxV =
            rows |> List.map (\( _, c ) -> toFloat c) |> List.maximum |> Maybe.withDefault 1

        viewRow i (( k, c ) as row) =
            let
                w =
                    if maxV == 0 then
                        0

                    else
                        toFloat c / maxV * toFloat chartW

                barClass =
                    if isUnknown k then
                        "bar bar-unknown"

                    else
                        "bar"
            in
            Svg.g
                [ SA.transform ("translate(0," ++ String.fromInt (i * rowH + 14) ++ ")")
                , SA.class "barrow clickable"
                , SE.onClick (onClickFn row)
                ]
                [ Svg.rect
                    [ SA.x "0"
                    , SA.y "-13"
                    , SA.width (String.fromInt (labelW + chartW))
                    , SA.height "26"
                    , SA.class "barhit"
                    ]
                    []
                , Svg.text_
                    [ SA.x (String.fromInt (labelW - 8))
                    , SA.y "0"
                    , SA.textAnchor "end"
                    , SA.dominantBaseline "middle"
                    , SA.class "barlabel"
                    ]
                    [ Svg.text (labelFn row) ]
                , Svg.rect
                    [ SA.x (String.fromInt labelW)
                    , SA.y "-9"
                    , SA.width (String.fromFloat w)
                    , SA.height "18"
                    , SA.class barClass
                    ]
                    []
                ]
    in
    Svg.svg
        [ SA.viewBox ("0 0 " ++ String.fromInt (labelW + chartW + 20) ++ " " ++ String.fromInt height)
        , SA.width (String.fromInt (labelW + chartW + 20))
        , SA.height (String.fromInt height)
        ]
        (List.indexedMap viewRow rows)



-- CHARTS


barChart : Maybe (a -> Msg) -> List a -> (a -> Float) -> (a -> String) -> Html Msg
barChart onClickFn rows valueOf labelOf =
    let
        n =
            List.length rows

        rowH =
            26

        labelW =
            340

        chartW =
            520

        height =
            n * rowH + 20

        maxV =
            rows |> List.map valueOf |> List.maximum |> Maybe.withDefault 1

        cursorClass =
            if onClickFn == Nothing then
                ""

            else
                " clickable"

        viewRow i row =
            let
                v =
                    valueOf row

                w =
                    if maxV == 0 then
                        0

                    else
                        v / maxV * toFloat chartW

                clickAttrs =
                    case onClickFn of
                        Nothing ->
                            []

                        Just fn ->
                            [ SE.onClick (fn row) ]
            in
            Svg.g
                (SA.transform ("translate(0," ++ String.fromInt (i * rowH + 14) ++ ")")
                    :: SA.class ("barrow" ++ cursorClass)
                    :: clickAttrs
                )
                [ Svg.rect
                    [ SA.x "0"
                    , SA.y "-13"
                    , SA.width (String.fromInt (labelW + chartW))
                    , SA.height "26"
                    , SA.class "barhit"
                    ]
                    []
                , Svg.text_
                    [ SA.x (String.fromInt (labelW - 8))
                    , SA.y "0"
                    , SA.textAnchor "end"
                    , SA.dominantBaseline "middle"
                    , SA.class "barlabel"
                    ]
                    [ Svg.text (labelOf row) ]
                , Svg.rect
                    [ SA.x (String.fromInt labelW)
                    , SA.y "-9"
                    , SA.width (String.fromFloat w)
                    , SA.height "18"
                    , SA.class "bar"
                    ]
                    []
                ]
    in
    Svg.svg
        [ SA.viewBox ("0 0 " ++ String.fromInt (labelW + chartW + 20) ++ " " ++ String.fromInt height)
        , SA.width (String.fromInt (labelW + chartW + 20))
        , SA.height (String.fromInt height)
        ]
        (List.indexedMap viewRow rows)


lineChart : List ( Int, Int ) -> Html msg
lineChart rows =
    let
        w =
            900

        h =
            320

        padL =
            44

        padR =
            12

        padT =
            16

        padB =
            32

        years =
            List.map Tuple.first rows

        counts =
            List.map Tuple.second rows

        minY =
            List.minimum years |> Maybe.withDefault 1901

        maxY =
            List.maximum years |> Maybe.withDefault 2024

        maxC =
            List.maximum counts |> Maybe.withDefault 1

        xScale year =
            if maxY == minY then
                toFloat padL

            else
                toFloat padL + toFloat (year - minY) / toFloat (maxY - minY) * toFloat (w - padL - padR)

        yScale c =
            toFloat (h - padB) - toFloat c / toFloat maxC * toFloat (h - padT - padB)

        path =
            rows
                |> List.indexedMap
                    (\i ( y, c ) ->
                        let
                            cmd =
                                if i == 0 then
                                    "M"

                                else
                                    "L"
                        in
                        cmd ++ String.fromFloat (xScale y) ++ "," ++ String.fromFloat (yScale c)
                    )
                |> String.join " "

        yTicks =
            tickValues 0 (toFloat maxC) 5

        xTicks =
            tickIntegers minY maxY 8

        gridY tick =
            Svg.g []
                [ Svg.line
                    [ SA.x1 (String.fromInt padL)
                    , SA.x2 (String.fromInt (w - padR))
                    , SA.y1 (String.fromFloat (yScale (round tick)))
                    , SA.y2 (String.fromFloat (yScale (round tick)))
                    , SA.class "grid"
                    ]
                    []
                , Svg.text_
                    [ SA.x (String.fromInt (padL - 6))
                    , SA.y (String.fromFloat (yScale (round tick)))
                    , SA.textAnchor "end"
                    , SA.dominantBaseline "middle"
                    , SA.class "axis"
                    ]
                    [ Svg.text (String.fromInt (round tick)) ]
                ]

        gridX year =
            Svg.g []
                [ Svg.line
                    [ SA.x1 (String.fromFloat (xScale year))
                    , SA.x2 (String.fromFloat (xScale year))
                    , SA.y1 (String.fromInt padT)
                    , SA.y2 (String.fromInt (h - padB))
                    , SA.class "grid"
                    ]
                    []
                , Svg.text_
                    [ SA.x (String.fromFloat (xScale year))
                    , SA.y (String.fromInt (h - padB + 16))
                    , SA.textAnchor "middle"
                    , SA.class "axis"
                    ]
                    [ Svg.text (String.fromInt year) ]
                ]
    in
    Svg.svg
        [ SA.viewBox ("0 0 " ++ String.fromInt w ++ " " ++ String.fromInt h)
        , SA.width (String.fromInt w)
        , SA.height (String.fromInt h)
        ]
        (List.map gridY yTicks
            ++ List.map gridX xTicks
            ++ [ Svg.path [ SA.d path, SA.class "line" ] [] ]
        )


stackedYearChart : Int -> Int -> List ( Int, ( Int, Int, Int ) ) -> Html Msg
stackedYearChart minY maxY rows =
    let
        w =
            900

        h =
            260

        padL =
            44

        padR =
            12

        padT =
            28

        padB =
            32

        years =
            max 1 (maxY - minY + 1)

        barW =
            toFloat (w - padL - padR) / toFloat years

        maxTotal =
            rows
                |> List.map (\( _, ( m, f, o ) ) -> m + f + o)
                |> List.maximum
                |> Maybe.withDefault 1

        yScale v =
            toFloat (h - padB) - toFloat v / toFloat maxTotal * toFloat (h - padT - padB)

        xPos year =
            toFloat padL + toFloat (year - minY) * barW

        viewBar ( year, ( m, f, o ) ) =
            let
                x =
                    xPos year

                drawW =
                    max 1 (barW - 0.5)

                yMale =
                    yScale m

                yFemale =
                    yScale (m + f)

                yOther =
                    yScale (m + f + o)

                hMale =
                    toFloat (h - padB) - yMale

                hFemale =
                    yMale - yFemale

                hOther =
                    yFemale - yOther
            in
            Svg.g [ SE.onClick (Select (SelYear year)), SA.class "barrow clickable" ]
                [ Svg.rect
                    [ SA.x (String.fromFloat x)
                    , SA.y (String.fromInt padT)
                    , SA.width (String.fromFloat drawW)
                    , SA.height (String.fromFloat (toFloat (h - padB) - toFloat padT))
                    , SA.class "barhit"
                    ]
                    []
                , Svg.rect
                    [ SA.x (String.fromFloat x)
                    , SA.y (String.fromFloat yMale)
                    , SA.width (String.fromFloat drawW)
                    , SA.height (String.fromFloat hMale)
                    , SA.class "bar-male"
                    ]
                    []
                , Svg.rect
                    [ SA.x (String.fromFloat x)
                    , SA.y (String.fromFloat yFemale)
                    , SA.width (String.fromFloat drawW)
                    , SA.height (String.fromFloat hFemale)
                    , SA.class "bar-female"
                    ]
                    []
                , Svg.rect
                    [ SA.x (String.fromFloat x)
                    , SA.y (String.fromFloat yOther)
                    , SA.width (String.fromFloat drawW)
                    , SA.height (String.fromFloat hOther)
                    , SA.class "bar-other"
                    ]
                    []
                , Svg.title [] [ Svg.text (String.fromInt year ++ ": " ++ String.fromInt (m + f + o) ++ " (M " ++ String.fromInt m ++ " · F " ++ String.fromInt f ++ " · ? " ++ String.fromInt o ++ ")") ]
                ]

        xLabels =
            tickIntegers minY maxY 8
                |> List.map
                    (\y ->
                        Svg.text_
                            [ SA.x (String.fromFloat (xPos y))
                            , SA.y (String.fromInt (h - padB + 16))
                            , SA.textAnchor "middle"
                            , SA.class "axis"
                            ]
                            [ Svg.text (String.fromInt y) ]
                    )

        legend =
            Svg.g [ SA.transform ("translate(" ++ String.fromInt padL ++ ",4)") ]
                [ swatch 0 "bar-male" "Male"
                , swatch 90 "bar-female" "Female"
                , swatch 180 "bar-other" "Org / unknown"
                ]
    in
    Svg.svg
        [ SA.viewBox ("0 0 " ++ String.fromInt w ++ " " ++ String.fromInt h)
        , SA.width "100%"
        , SA.height (String.fromInt h)
        ]
        (legend :: List.map viewBar rows ++ xLabels)


swatch : Int -> String -> String -> Svg msg
swatch xOffset cls lbl =
    Svg.g [ SA.transform ("translate(" ++ String.fromInt xOffset ++ ",0)") ]
        [ Svg.rect [ SA.x "0", SA.y "0", SA.width "12", SA.height "12", SA.class cls ] []
        , Svg.text_ [ SA.x "16", SA.y "10", SA.class "axis" ] [ Svg.text lbl ]
        ]


tickValues : Float -> Float -> Int -> List Float
tickValues lo hi n =
    let
        step =
            (hi - lo) / toFloat n
    in
    List.range 0 n |> List.map (\i -> lo + step * toFloat i)


tickIntegers : Int -> Int -> Int -> List Int
tickIntegers lo hi n =
    let
        step =
            max 1 ((hi - lo) // n)
    in
    List.range 0 n |> List.map (\i -> lo + step * i) |> List.filter (\v -> v <= hi)


formatFloat : Int -> Float -> String
formatFloat decimals f =
    let
        mult =
            toFloat (10 ^ decimals)

        rounded =
            toFloat (round (f * mult)) / mult
    in
    String.fromFloat rounded



-- STYLE


styles : String
styles =
    """
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; background: #fafaf7; color: #222; }
    .wrap { max-width: 980px; margin: 0 auto; padding: 24px; }
    h1 { margin: 0 0 4px; font-size: 28px; }
    h2 { margin: 24px 0 8px; font-size: 18px; color: #333; }
    .muted { color: #777; font-size: 13px; }
    .controls { display: flex; gap: 16px; flex-wrap: wrap; margin: 16px 0 8px; align-items: center; }
    .controls label { font-size: 13px; color: #444; }
    .controls input[type=number] { width: 80px; padding: 4px 6px; font-size: 13px; }
    .controls select { padding: 4px 6px; font-size: 13px; }
    .tabs { display: flex; gap: 4px; border-bottom: 1px solid #ddd; margin-bottom: 12px; flex-wrap: wrap; }
    .tab { background: none; border: none; padding: 8px 14px; cursor: pointer; font-size: 14px; color: #555; border-bottom: 2px solid transparent; }
    .tab.active { color: #b58400; border-bottom-color: #b58400; font-weight: 600; }
    .summary { font-size: 13px; color: #666; margin: 4px 0 8px; }
    .loading, .error { padding: 32px 0; color: #888; font-style: italic; }
    .error { color: #b00; font-style: normal; }
    .barlabel { font-size: 12px; fill: #333; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
    .bar { fill: #b58400; }
    .bar-unknown { fill: #bdbdbd; }
    .barrow.clickable:hover .bar-unknown { fill: #9e9e9e; }
    .line { fill: none; stroke: #b58400; stroke-width: 2; }
    .grid { stroke: #eee; stroke-width: 1; }
    .axis { font-size: 11px; fill: #888; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
    .bar-male { fill: #4a86c5; }
    .bar-female { fill: #d96a7a; }
    .bar-other { fill: #aaa; }
    .warning { background: #fff8e6; border-left: 3px solid #b58400; padding: 8px 12px; margin: 8px 0; font-size: 12.5px; color: #5a4500; }
    .barhit { fill: transparent; }
    .barrow.clickable { cursor: pointer; }
    .barrow.clickable:hover .bar { fill: #d49d12; }
    .barrow.clickable:hover .barhit { fill: #f3e6c3; }
    .barrow.clickable:hover .bar-male { fill: #79a8d8; }
    .barrow.clickable:hover .bar-female { fill: #e88a96; }
    .barrow.clickable:hover .bar-other { fill: #c8c8c8; }
    .drilldown { margin-top: 24px; padding: 16px; background: #fff; border: 1px solid #e3e3dc; border-radius: 4px; }
    .drilldown-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .drilldown-title { font-weight: 600; color: #333; }
    .clear-btn { background: none; border: 1px solid #ccc; color: #555; padding: 3px 10px; font-size: 12px; cursor: pointer; border-radius: 3px; }
    .clear-btn:hover { background: #f3f3f0; }
    .laureate-list { list-style: none; padding: 0; margin: 0; max-height: 480px; overflow-y: auto; }
    .laureate { padding: 4px 0; font-size: 13px; border-bottom: 1px solid #f0f0eb; }
    .laureate-name { font-weight: 600; color: #222; }
    .laureate-meta { color: #555; }
    .laureate-extra { color: #888; font-size: 12px; }
    .wiki-link { margin-left: 8px; color: #b58400; font-size: 11px; text-decoration: none; }
    .wiki-link:hover { text-decoration: underline; }
    .yearly-chart { background: #fafaf7; border: 1px solid #f0f0eb; border-radius: 3px; margin-bottom: 12px; }
    """



-- MAIN


main : Program () Model Msg
main =
    Browser.element
        { init = init
        , update = update
        , view = view
        , subscriptions = \_ -> Sub.none
        }
