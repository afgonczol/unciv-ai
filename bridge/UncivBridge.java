package bridge;

import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.backends.headless.HeadlessFiles;
import com.unciv.Constants;
import com.unciv.UncivGame;
import com.unciv.logic.GameInfo;
import com.unciv.logic.GameStarter;
import com.unciv.logic.city.City;
import com.unciv.logic.city.CityFocus;
import com.unciv.logic.city.managers.CityFounder;
import com.unciv.logic.civilization.Civilization;
import com.unciv.logic.civilization.Notification;
import com.unciv.logic.civilization.PlayerType;
import com.unciv.logic.civilization.diplomacy.DeclareWarReason;
import com.unciv.logic.civilization.diplomacy.DiplomacyManager;
import com.unciv.logic.civilization.diplomacy.DiplomaticStatus;
import com.unciv.logic.civilization.diplomacy.WarType;
import com.unciv.logic.files.UncivFiles;
import com.unciv.logic.map.HexCoord;
import com.unciv.logic.map.MapSize;
import com.unciv.logic.map.MapShape;
import com.unciv.logic.map.TileMap;
import com.unciv.logic.map.mapunit.MapUnit;
import com.unciv.logic.map.tile.Tile;
import com.unciv.models.metadata.GameSetupInfo;
import com.unciv.models.metadata.Player;
import com.unciv.models.ruleset.Building;
import com.unciv.models.ruleset.Policy;
import com.unciv.models.ruleset.RulesetCache;
import com.unciv.models.ruleset.tech.Technology;
import com.unciv.models.ruleset.unit.BaseUnit;
import com.unciv.models.stats.Stat;
import com.unciv.ui.screens.victoryscreen.RankingType;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class UncivBridge {

    private static GameInfo gameInfo = null;
    private static boolean initialized = false;
    private static PrintStream jsonOut;
    private static ServerSocket serverSocket;

    public static synchronized void initEngine() {
        if (initialized) return;
        try {
            Gdx.files = new HeadlessFiles();
            UncivGame game = new UncivGame(true);
            UncivGame.Current = game;
            game.setFiles(new UncivFiles(Gdx.files, null));
            game.setSettings(new com.unciv.models.metadata.GameSettings());
            game.getSettings().setShowTutorials(false);
            RulesetCache.INSTANCE.loadRulesets(false, true);
            com.unciv.models.tilesets.TileSetCache.INSTANCE.loadTileSetConfigs(true);
            com.unciv.models.skins.SkinCache.INSTANCE.loadSkinConfigs(true);
            initialized = true;
        } catch (Exception e) {
            System.err.println("Error initializing Unciv engine: " + e.getMessage());
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        initEngine();

        if (args.length > 0 && args[0].equals("--test")) {
            runSelfTest();
            return;
        }

        runSocketServer(args);
    }

    private static void runSocketServer(String[] args) {
        int requestedPort = 0;
        if (args.length > 0) {
            try {
                requestedPort = Integer.parseInt(args[0]);
            } catch (NumberFormatException ignored) {}
        }

        try {
            serverSocket = new ServerSocket(requestedPort, 10, InetAddress.getByName("127.0.0.1"));
            int port = serverSocket.getLocalPort();
            System.out.println("Bridge listening on 127.0.0.1:" + port);
            System.out.flush();

            while (!serverSocket.isClosed()) {
                try {
                    Socket socket = serverSocket.accept();
                    socket.setTcpNoDelay(true);
                    new Thread(() -> handleClient(socket), "UncivBridgeClientThread").start();
                } catch (IOException e) {
                    if (serverSocket.isClosed()) break;
                }
            }
        } catch (Exception e) {
            System.err.println("Socket server fatal error: " + e.getMessage());
            e.printStackTrace();
        }
    }

    private static void handleClient(Socket socket) {
        try {
            socket.setTcpNoDelay(true);
            InputStream in = socket.getInputStream();
            OutputStream out = socket.getOutputStream();
            ByteArrayOutputStream lineBuf = new ByteArrayOutputStream();

            int b;
            while ((b = in.read()) != -1) {
                if (b == '\n') {
                    String line = lineBuf.toString(StandardCharsets.UTF_8).trim();
                    lineBuf.reset();
                    if (line.isEmpty()) continue;
                    if (line.equals("exit") || line.equals("quit")) {
                        byte[] bye = "{\"status\":\"ok\",\"message\":\"bye\"}\n".getBytes(StandardCharsets.UTF_8);
                        out.write(bye);
                        out.flush();
                        break;
                    }

                    String response;
                    try {
                        response = handleJsonRequest(line);
                    } catch (Throwable t) {
                        StringWriter sw = new StringWriter();
                        t.printStackTrace(new PrintWriter(sw));
                        Map<String, Object> err = new HashMap<>();
                        err.put("status", "error");
                        err.put("error", "Exception in handleJsonRequest: " + t.toString() + "\n" + sw.toString());
                        response = toJson(err);
                    }
                    byte[] respBytes = (response + "\n").getBytes(StandardCharsets.UTF_8);
                    out.write(respBytes);
                    out.flush();
                } else if (b != '\r') {
                    lineBuf.write(b);
                }
            }
        } catch (Exception ignored) {
        } finally {
            try { socket.close(); } catch (Exception ignored) {}
        }
    }

    private static void runSelfTest() {
        System.err.println("Running self-test...");
        String newGameReq = "{\"command\":\"new_game\",\"nation\":\"Rome\",\"difficulty\":\"Chieftain\",\"ruleset\":\"Civ V - Vanilla\"}";
        String res = handleJsonRequest(newGameReq);
        jsonOut.println(res);
        jsonOut.flush();
        System.exit(0);
    }

    public static String handleJsonRequest(String jsonStr) {
        try {
            Map<String, Object> req = parseSimpleJson(jsonStr);
            String command = (String) req.getOrDefault("command", "");
            Map<String, Object> response = new LinkedHashMap<>();

            switch (command) {
                case "ping":
                    response.put("status", "ok");
                    response.put("message", "pong");
                    break;

                case "new_game": {
                    String nation = (String) req.getOrDefault("nation", "");
                    String difficulty = (String) req.getOrDefault("difficulty", "Prince");
                    String rulesetName = (String) req.getOrDefault("ruleset", "Civ V - Vanilla");
                    String mapSizeStr = (String) req.getOrDefault("map_size", "Tiny");
                    
                    GameSetupInfo setup = new GameSetupInfo();
                    setup.getGameParameters().setBaseRuleset(rulesetName);
                    setup.getMapParameters().setBaseRuleset(rulesetName);
                    setup.getGameParameters().setDifficulty(difficulty);
                    setup.getMapParameters().setShape(MapShape.rectangular);
                    setup.getMapParameters().setWorldWrap(true);
                    setup.getMapParameters().setStrategicBalance(true);
                    setup.getMapParameters().setLegendaryStart(true);

                    if (mapSizeStr.equalsIgnoreCase("Tiny")) {
                        setup.getMapParameters().setMapSize(MapSize.Companion.getTiny());
                        setup.getGameParameters().setNumberOfCityStates(2);
                    } else if (mapSizeStr.equalsIgnoreCase("Small")) {
                        setup.getMapParameters().setMapSize(MapSize.Companion.getSmall());
                        setup.getGameParameters().setNumberOfCityStates(6);
                    } else if (mapSizeStr.equalsIgnoreCase("Large")) {
                        setup.getMapParameters().setMapSize(MapSize.Companion.getLarge());
                        setup.getGameParameters().setNumberOfCityStates(12);
                    } else if (mapSizeStr.equalsIgnoreCase("Huge")) {
                        setup.getMapParameters().setMapSize(MapSize.Companion.getHuge());
                        setup.getGameParameters().setNumberOfCityStates(16);
                    } else {
                        setup.getMapParameters().setMapSize(MapSize.Companion.getMedium());
                        setup.getGameParameters().setNumberOfCityStates(8);
                    }

                    setup.getGameParameters().getPlayers().clear();
                    Player human = new Player();
                    human.setChosenCiv(nation.isEmpty() ? "Rome" : nation);
                    human.setPlayerType(PlayerType.Human);
                    setup.getGameParameters().getPlayers().add(human);

                    for (int i = 0; i < 3; i++) {
                        Player ai = new Player();
                        ai.setChosenCiv(Constants.random);
                        ai.setPlayerType(PlayerType.AI);
                        setup.getGameParameters().getPlayers().add(ai);
                    }

                    gameInfo = GameStarter.Companion.startNewGame(setup);
                    gameInfo.setTransients();

                    response.put("status", "ok");
                    response.put("message", "Game created successfully");
                    response.put("active_civ", gameInfo.getCurrentPlayerCivilization().getCivName());
                    response.put("turn", gameInfo.getTurns());
                    break;
                }

                case "load_game": {
                    String saveData = (String) req.getOrDefault("save_data", "");
                    if (saveData.isEmpty()) {
                        response.put("status", "error");
                        response.put("error", "Empty save data");
                        break;
                    }
                    gameInfo = UncivFiles.Companion.gameInfoFromString(saveData);
                    gameInfo.setTransients();
                    response.put("status", "ok");
                    response.put("message", "Game loaded successfully");
                    response.put("active_civ", gameInfo.getCurrentPlayerCivilization().getCivName());
                    response.put("turn", gameInfo.getTurns());
                    break;
                }

                case "save_game": {
                    if (gameInfo == null) {
                        response.put("status", "error");
                        response.put("error", "No active game");
                        break;
                    }
                    String saveString = UncivFiles.Companion.gameInfoToString(gameInfo, Boolean.FALSE, false);
                    response.put("status", "ok");
                    response.put("save_data", saveString);
                    break;
                }

                case "get_state": {
                    if (gameInfo == null) {
                        response.put("status", "error");
                        response.put("error", "No active game");
                        break;
                    }
                    response.put("status", "ok");
                    response.put("game", buildGameState(gameInfo));
                    break;
                }

                case "get_map": {
                    if (gameInfo == null) {
                        response.put("status", "error");
                        response.put("error", "No active game");
                        break;
                    }
                    int centerX = ((Number) req.getOrDefault("center_x", 0)).intValue();
                    int centerY = ((Number) req.getOrDefault("center_y", 0)).intValue();
                    int radius = ((Number) req.getOrDefault("radius", 6)).intValue();
                    try {
                        response.put("map", buildMapData(gameInfo, centerX, centerY, radius));
                        response.put("status", "ok");
                    } catch (Throwable t) {
                        StringWriter sw = new StringWriter();
                        t.printStackTrace(new PrintWriter(sw));
                        response.put("status", "error");
                        response.put("error", "buildMapData error: " + t.toString() + "\n" + sw.toString());
                    }
                    break;
                }

                case "unit_action": {
                    if (gameInfo == null) {
                        response.put("status", "error");
                        response.put("error", "No active game");
                        break;
                    }
                    int unitId = ((Number) req.getOrDefault("unit_id", -1)).intValue();
                    String action = (String) req.getOrDefault("action", "");
                    int targetX = ((Number) req.getOrDefault("target_x", 0)).intValue();
                    int targetY = ((Number) req.getOrDefault("target_y", 0)).intValue();
                    String param = (String) req.getOrDefault("param", "");

                    Map<String, Object> actionResult = executeUnitAction(gameInfo, unitId, action, targetX, targetY, param);
                    response.putAll(actionResult);
                    break;
                }

                case "city_action": {
                    if (gameInfo == null) {
                        response.put("status", "error");
                        response.put("error", "No active game");
                        break;
                    }
                    String cityName = (String) req.getOrDefault("city_name", "");
                    String action = (String) req.getOrDefault("action", "");
                    String param = (String) req.getOrDefault("param", "");
                    int targetX = ((Number) req.getOrDefault("target_x", 0)).intValue();
                    int targetY = ((Number) req.getOrDefault("target_y", 0)).intValue();

                    Map<String, Object> actionResult = executeCityAction(gameInfo, cityName, action, param, targetX, targetY);
                    response.putAll(actionResult);
                    break;
                }

                case "choose_tech": {
                    if (gameInfo == null) {
                        response.put("status", "error");
                        response.put("error", "No active game");
                        break;
                    }
                    String techName = (String) req.getOrDefault("tech_name", "");
                    Civilization player = gameInfo.getCurrentPlayerCivilization();
                    if (!player.getTech().canBeResearched(techName)) {
                        response.put("status", "error");
                        response.put("error", "Technology " + techName + " cannot be researched yet");
                    } else {
                        player.getTech().getTechsToResearch().clear();
                        player.getTech().getTechsToResearch().add(techName);
                        response.put("status", "ok");
                        response.put("message", "Now researching " + techName);
                        response.put("turns_left", player.getTech().turnsToTech(techName));
                    }
                    break;
                }

                case "adopt_policy": {
                    if (gameInfo == null) {
                        response.put("status", "error");
                        response.put("error", "No active game");
                        break;
                    }
                    String policyName = (String) req.getOrDefault("policy_name", "");
                    Civilization player = gameInfo.getCurrentPlayerCivilization();
                    Policy policy = player.getGameInfo().getRuleset().getPolicies().get(policyName);
                    if (policy == null) {
                        response.put("status", "error");
                        response.put("error", "Unknown policy " + policyName);
                    } else if (!player.getPolicies().isAdoptable(policy, false)) {
                        response.put("status", "error");
                        response.put("error", "Policy " + policyName + " is not currently adoptable");
                    } else {
                        player.getPolicies().adopt(policy, false);
                        response.put("status", "ok");
                        response.put("message", "Adopted policy " + policyName);
                    }
                    break;
                }

                case "diplomacy_action": {
                    if (gameInfo == null) {
                        response.put("status", "error");
                        response.put("error", "No active game");
                        break;
                    }
                    String targetCiv = (String) req.getOrDefault("target_civ", "");
                    String action = (String) req.getOrDefault("action", "");
                    Civilization player = gameInfo.getCurrentPlayerCivilization();
                    Civilization other = gameInfo.getCivilizationOrNull(targetCiv);
                    if (other == null) {
                        response.put("status", "error");
                        response.put("error", "Unknown civilization " + targetCiv);
                        break;
                    }
                    DiplomacyManager dip = player.getDiplomacyManager(other);
                    if (dip == null) {
                        response.put("status", "error");
                        response.put("error", "Cannot interact with " + targetCiv);
                        break;
                    }

                    if (action.equalsIgnoreCase("declare_war")) {
                        dip.declareWar(new DeclareWarReason(WarType.DirectWar, null));
                        response.put("status", "ok");
                        response.put("message", "Declared war on " + targetCiv);
                    } else if (action.equalsIgnoreCase("make_peace")) {
                        dip.makePeace();
                        response.put("status", "ok");
                        response.put("message", "Made peace with " + targetCiv);
                    } else {
                        response.put("status", "error");
                        response.put("error", "Unsupported diplomacy action: " + action);
                    }
                    break;
                }

                case "end_turn": {
                    if (gameInfo == null) {
                        response.put("status", "error");
                        response.put("error", "No active game");
                        break;
                    }
                    int oldTurn = gameInfo.getTurns();
                    Civilization player = gameInfo.getCurrentPlayerCivilization();

                    // Advance turn
                    gameInfo.nextTurn(null, false);
                    int newTurn = gameInfo.getTurns();

                    List<String> newNotifications = new ArrayList<>();
                    for (Notification n : player.getNotifications()) {
                        newNotifications.add(n.getText());
                    }

                    response.put("status", "ok");
                    response.put("old_turn", oldTurn);
                    response.put("new_turn", newTurn);
                    response.put("notifications", newNotifications);
                    response.put("active_civ", gameInfo.getCurrentPlayerCivilization().getCivName());
                    break;
                }

                default:
                    response.put("status", "error");
                    response.put("error", "Unknown command: " + command);
                    break;
            }

            return toJson(response);
        } catch (Throwable e) {
            Map<String, Object> err = new HashMap<>();
            err.put("status", "error");
            err.put("error", e.getMessage() != null ? e.getMessage() : e.toString());
            return toJson(err);
        }
    }

    private static Map<String, Object> executeUnitAction(GameInfo game, int unitId, String action, int targetX, int targetY, String param) {
        Map<String, Object> res = new HashMap<>();
        Civilization player = game.getCurrentPlayerCivilization();
        MapUnit targetUnit = null;

        Iterator<MapUnit> it = player.getUnits().getCivUnits().iterator();
        while (it.hasNext()) {
            MapUnit u = it.next();
            if (u.getId() == unitId) {
                targetUnit = u;
                break;
            }
        }

        if (targetUnit == null) {
            res.put("status", "error");
            res.put("error", "Unit not found with ID " + unitId);
            return res;
        }

        HexCoord targetCoord = new HexCoord(targetX, targetY);
        Tile targetTile = game.getTileMap().get(targetCoord);

        try {
            switch (action.toLowerCase()) {
                case "move": {
                    if (targetTile == null) {
                        res.put("status", "error");
                        res.put("error", "Target tile does not exist");
                        return res;
                    }
                    targetUnit.getMovement().headTowards(targetTile);
                    res.put("status", "ok");
                    res.put("message", "Unit " + targetUnit.getName() + " moved towards (" + targetX + ", " + targetY + ")");
                    res.put("new_location", Arrays.asList(targetUnit.getTile().getPosition().getX(), targetUnit.getTile().getPosition().getY()));
                    res.put("movement_left", targetUnit.getCurrentMovement());
                    break;
                }

                case "attack": {
                    if (targetTile == null) {
                        res.put("status", "error");
                        res.put("error", "Target tile does not exist");
                        return res;
                    }
                    if (targetUnit.getTile().getPosition().equals(targetCoord)) {
                        res.put("status", "error");
                        res.put("error", "Cannot attack own tile");
                        return res;
                    }
                    targetUnit.getMovement().headTowards(targetTile);
                    res.put("status", "ok");
                    res.put("message", "Unit " + targetUnit.getName() + " attacked target at (" + targetX + ", " + targetY + ")");
                    res.put("current_health", targetUnit.getHealth());
                    res.put("movement_left", targetUnit.getCurrentMovement());
                    break;
                }

                case "found_city": {
                    if (!targetUnit.getName().equals("Settler")) {
                        res.put("status", "error");
                        res.put("error", "Only Settlers can found cities");
                        return res;
                    }
                    Tile tile = targetUnit.getTile();
                    City city = new CityFounder().foundCity(player, tile.getPosition(), targetUnit);
                    targetUnit.removeFromTile();
                    player.getUnits().removeUnit(targetUnit, true);
                    res.put("status", "ok");
                    res.put("message", "City founded: " + city.getName() + " at (" + tile.getPosition().getX() + ", " + tile.getPosition().getY() + ")");
                    res.put("city_name", city.getName());
                    break;
                }

                case "improve":
                case "improve_tile": {
                    if (param.isEmpty()) {
                        res.put("status", "error");
                        res.put("error", "No improvement specified (e.g. Farm, Mine, Road)");
                        return res;
                    }
                    Tile tile = targetUnit.getTile();
                    tile.setImprovement(param, player, targetUnit);
                    targetUnit.useMovementPoints(targetUnit.getCurrentMovement());
                    res.put("status", "ok");
                    res.put("message", "Started improvement " + param + " on tile (" + tile.getPosition().getX() + ", " + tile.getPosition().getY() + ")");
                    break;
                }

                case "fortify": {
                    targetUnit.setAction("Fortify");
                    res.put("status", "ok");
                    res.put("message", "Unit " + targetUnit.getName() + " fortified");
                    break;
                }

                case "sleep": {
                    targetUnit.setAction("Sleep");
                    res.put("status", "ok");
                    res.put("message", "Unit " + targetUnit.getName() + " is now sleeping");
                    break;
                }

                case "wake": {
                    targetUnit.setAction(null);
                    res.put("status", "ok");
                    res.put("message", "Unit " + targetUnit.getName() + " awakened");
                    break;
                }

                case "promote": {
                    if (param.isEmpty()) {
                        res.put("status", "error");
                        res.put("error", "No promotion specified");
                        return res;
                    }
                    targetUnit.getPromotions().addPromotion(param, true);
                    res.put("status", "ok");
                    res.put("message", "Promoted unit with " + param);
                    break;
                }

                case "automate": {
                    targetUnit.setAutomated(true);
                    res.put("status", "ok");
                    res.put("message", "Unit automated");
                    break;
                }

                case "disband": {
                    targetUnit.disband();
                    res.put("status", "ok");
                    res.put("message", "Unit disbanded");
                    break;
                }

                default:
                    res.put("status", "error");
                    res.put("error", "Unknown unit action: " + action);
                    break;
            }
        } catch (Exception e) {
            res.put("status", "error");
            res.put("error", e.getMessage() != null ? e.getMessage() : e.toString());
        }

        return res;
    }

    private static Map<String, Object> executeCityAction(GameInfo game, String cityName, String action, String param, int targetX, int targetY) {
        Map<String, Object> res = new HashMap<>();
        Civilization player = game.getCurrentPlayerCivilization();
        City targetCity = null;

        for (City c : player.getCities()) {
            if (c.getName().equalsIgnoreCase(cityName)) {
                targetCity = c;
                break;
            }
        }

        if (targetCity == null && !player.getCities().isEmpty()) {
            targetCity = player.getCities().get(0);
        }

        if (targetCity == null) {
            res.put("status", "error");
            res.put("error", "No cities owned by active player");
            return res;
        }

        try {
            switch (action.toLowerCase()) {
                case "set_production": {
                    if (param.isEmpty()) {
                        res.put("status", "error");
                        res.put("error", "No construction item specified");
                        return res;
                    }
                    targetCity.getCityConstructions().getConstructionQueue().clear();
                    targetCity.getCityConstructions().getConstructionQueue().add(param);
                    res.put("status", "ok");
                    res.put("message", "Set production in " + targetCity.getName() + " to " + param);
                    res.put("turns_left", targetCity.getCityConstructions().turnsToConstruction(param, true));
                    break;
                }

                case "add_to_queue": {
                    if (param.isEmpty()) {
                        res.put("status", "error");
                        res.put("error", "No construction item specified");
                        return res;
                    }
                    targetCity.getCityConstructions().getConstructionQueue().add(param);
                    res.put("status", "ok");
                    res.put("message", "Added " + param + " to queue in " + targetCity.getName());
                    res.put("queue", new ArrayList<>(targetCity.getCityConstructions().getConstructionQueue()));
                    break;
                }

                case "purchase": {
                    if (param.isEmpty()) {
                        res.put("status", "error");
                        res.put("error", "No purchase item specified");
                        return res;
                    }
                    boolean success = targetCity.getCityConstructions().purchaseConstruction(param, 0, false, Stat.Gold, null);
                    if (success) {
                        res.put("status", "ok");
                        res.put("message", "Purchased " + param + " in " + targetCity.getName());
                    } else {
                        res.put("status", "error");
                        res.put("error", "Could not purchase " + param + " (insufficient gold or invalid item)");
                    }
                    break;
                }

                case "set_focus": {
                    try {
                        CityFocus focus = CityFocus.valueOf(param);
                        targetCity.setCityFocus(focus);
                        targetCity.reassignPopulation(false);
                        res.put("status", "ok");
                        res.put("message", "City focus set to " + param);
                    } catch (Exception e) {
                        res.put("status", "error");
                        res.put("error", "Invalid city focus: " + param);
                    }
                    break;
                }

                default:
                    res.put("status", "error");
                    res.put("error", "Unknown city action: " + action);
                    break;
            }
        } catch (Exception e) {
            res.put("status", "error");
            res.put("error", e.getMessage() != null ? e.getMessage() : e.toString());
        }

        return res;
    }

    private static Map<String, Object> buildGameState(GameInfo game) {
        Map<String, Object> state = new LinkedHashMap<>();
        Civilization player = game.getCurrentPlayerCivilization();

        state.put("turn", game.getTurns());
        state.put("difficulty", game.getGameParameters().getDifficulty());
        state.put("speed", game.getSpeed().getName());
        state.put("active_civ", player.getCivName());
        state.put("nation", player.getNation().getName());

        // Stats
        Map<String, Object> stats = new LinkedHashMap<>();
        stats.put("gold", player.getGold());
        stats.put("gold_per_turn", player.getStats().getStatsForNextTurn().getGold());
        stats.put("science_per_turn", player.getStats().getStatsForNextTurn().getScience());
        stats.put("culture_per_turn", player.getStats().getStatsForNextTurn().getCulture());
        stats.put("faith_per_turn", player.getStats().getStatsForNextTurn().getFaith());
        stats.put("happiness", player.getHappiness());
        stats.put("score", player.getStatForRanking(RankingType.Score));
        state.put("stats", stats);

        // Tech
        Map<String, Object> techMap = new LinkedHashMap<>();
        String curTech = player.getTech().currentTechnologyName();
        techMap.put("current_tech", curTech != null ? curTech : "None");
        if (curTech != null) {
            techMap.put("turns_to_finish", player.getTech().turnsToTech(curTech));
            techMap.put("science_progress", player.getTech().researchOfTech(curTech));
            techMap.put("science_cost", player.getTech().costOfTech(curTech));
        }

        List<String> researched = new ArrayList<>(player.getTech().getTechsResearched());
        techMap.put("researched_techs", researched);

        List<Map<String, Object>> researchable = new ArrayList<>();
        for (Technology tech : game.getRuleset().getTechnologies().values()) {
            if (player.getTech().canBeResearched(tech.getName()) && !player.getTech().isResearched(tech.getName())) {
                Map<String, Object> t = new LinkedHashMap<>();
                t.put("name", tech.getName());
                t.put("cost", player.getTech().costOfTech(tech.getName()));
                t.put("turns", player.getTech().turnsToTech(tech.getName()));
                t.put("prerequisites", new ArrayList<>(tech.getPrerequisites()));
                researchable.add(t);
            }
        }
        techMap.put("researchable_techs", researchable);
        state.put("technology", techMap);

        // Policies
        Map<String, Object> polMap = new LinkedHashMap<>();
        polMap.put("adopted_policies", new ArrayList<>(player.getPolicies().getAdoptedPolicies()));
        List<String> adoptable = new ArrayList<>();
        for (Policy p : game.getRuleset().getPolicies().values()) {
            if (player.getPolicies().isAdoptable(p, false)) {
                adoptable.add(p.getName());
            }
        }
        polMap.put("adoptable_policies", adoptable);
        polMap.put("culture_needed", player.getPolicies().getCultureNeededForNextPolicy());
        state.put("policies", polMap);

        // Cities
        List<Map<String, Object>> cityList = new ArrayList<>();
        for (City c : player.getCities()) {
            Map<String, Object> cityData = new LinkedHashMap<>();
            cityData.put("name", c.getName());
            cityData.put("location", Arrays.asList(c.getLocation().getX(), c.getLocation().getY()));
            cityData.put("population", c.getPopulation().getPopulation());
            cityData.put("health", c.getHealth());
            cityData.put("max_health", 200);
            cityData.put("defense", c.getStrength());
            cityData.put("food_stored", c.getPopulation().getFoodStored());
            cityData.put("food_needed", c.getPopulation().getFoodToNextPopulation());
            cityData.put("food_per_turn", c.getCityStats().getCurrentCityStats().getFood());
            cityData.put("production_per_turn", c.getCityStats().getCurrentCityStats().getProduction());
            cityData.put("gold_per_turn", c.getCityStats().getCurrentCityStats().getGold());
            cityData.put("science_per_turn", c.getCityStats().getCurrentCityStats().getScience());
            cityData.put("culture_per_turn", c.getCityStats().getCurrentCityStats().getCulture());
            cityData.put("faith_per_turn", c.getCityStats().getCurrentCityStats().getFaith());

            cityData.put("current_construction", c.getCityConstructions().currentConstructionName());
            if (!c.getCityConstructions().currentConstructionName().isEmpty()) {
                cityData.put("turns_to_finish", c.getCityConstructions().turnsToConstruction(c.getCityConstructions().currentConstructionName(), true));
            }
            cityData.put("queue", new ArrayList<>(c.getCityConstructions().getConstructionQueue()));

            // Buildables
            List<String> bUnits = new ArrayList<>();
            for (BaseUnit bu : game.getRuleset().getUnits().values()) {
                BaseUnit equiv = player.getEquivalentUnit(bu);
                if (equiv.isBuildable(c.getCityConstructions())) {
                    bUnits.add(equiv.getName() + " (" + equiv.getCost() + "p)");
                }
            }
            cityData.put("buildable_units", bUnits);

            List<String> bBuildings = new ArrayList<>();
            for (Building bb : game.getRuleset().getBuildings().values()) {
                Building equiv = player.getEquivalentBuilding(bb);
                if (equiv.isBuildable(c.getCityConstructions())) {
                    bBuildings.add(equiv.getName() + " (" + equiv.getCost() + "p)");
                }
            }
            cityData.put("buildable_buildings", bBuildings);

            cityList.add(cityData);
        }
        state.put("cities", cityList);

        // Units
        List<Map<String, Object>> unitList = new ArrayList<>();
        Iterator<MapUnit> uIt = player.getUnits().getCivUnits().iterator();
        while (uIt.hasNext()) {
            MapUnit u = uIt.next();
            if (u == null) continue;
            Map<String, Object> uData = new LinkedHashMap<>();
            uData.put("id", u.getId());
            uData.put("name", u.getName());
            if (u.hasTile() && u.getTile() != null && u.getTile().getPosition() != null) {
                uData.put("location", Arrays.asList(u.getTile().getPosition().getX(), u.getTile().getPosition().getY()));
            } else {
                uData.put("location", Arrays.asList(0, 0));
            }
            uData.put("health", u.getHealth());
            uData.put("max_health", 100);
            uData.put("movement", u.getCurrentMovement());
            uData.put("max_movement", u.getMaxMovement(false));
            uData.put("is_military", u.isMilitary());
            uData.put("is_civilian", u.isCivilian());
            uData.put("is_idle", u.isIdle(false));
            uData.put("is_fortified", u.isFortified());
            uData.put("is_sleeping", u.isSleeping());

            List<String> actions = new ArrayList<>();
            if (u.getCurrentMovement() > 0) {
                actions.add("move");
                if (u.isMilitary()) actions.add("attack");
                if (u.getName().equals("Settler")) actions.add("found_city");
                if (u.getName().equals("Worker")) actions.add("improve_tile");
                actions.add("fortify");
                actions.add("sleep");
                actions.add("disband");
            }
            uData.put("available_actions", actions);
            unitList.add(uData);
        }
        state.put("units", unitList);

        // Diplomacy
        List<Map<String, Object>> dipList = new ArrayList<>();
        for (Civilization other : game.getCivilizations()) {
            if (other == player || other.isBarbarian()) continue;
            if (player.knows(other)) {
                Map<String, Object> dData = new LinkedHashMap<>();
                dData.put("civ_name", other.getCivName());
                dData.put("is_city_state", other.isCityState());
                dData.put("is_alive", other.isAlive());
                DiplomacyManager dip = player.getDiplomacyManager(other);
                if (dip != null) {
                    dData.put("is_at_war", dip.getDiplomaticStatus() == DiplomaticStatus.War);
                    dData.put("status", dip.getDiplomaticStatus().name());
                }
                dipList.add(dData);
            }
        }
        state.put("known_civilizations", dipList);

        // Notifications
        List<String> notifs = new ArrayList<>();
        for (Notification n : player.getNotifications()) {
            notifs.add(n.getText());
        }
        state.put("notifications", notifs);

        return state;
    }

    private static Map<String, Object> buildMapData(GameInfo game, int centerX, int centerY, int radius) {
        Map<String, Object> mapRes = new LinkedHashMap<>();
        Civilization player = game.getCurrentPlayerCivilization();
        TileMap tileMap = game.getTileMap();

        HexCoord center = new HexCoord(centerX, centerY);
        if (centerX == 0 && centerY == 0) {
            if (!player.getCities().isEmpty()) {
                center = player.getCities().get(0).getLocation();
            } else {
                Iterator<MapUnit> it = player.getUnits().getCivUnits().iterator();
                while (it.hasNext()) {
                    MapUnit u = it.next();
                    if (u != null && u.hasTile() && u.getTile() != null && u.getTile().getPosition() != null) {
                        center = u.getTile().getPosition();
                        break;
                    }
                }
            }
        }

        int minX = center.getX() - radius;
        int maxX = center.getX() + radius;
        int minY = center.getY() - radius;
        int maxY = center.getY() + radius;

        StringBuilder asciiGrid = new StringBuilder();
        List<Map<String, Object>> tileDetails = new ArrayList<>();

        asciiGrid.append("Map Grid (Radius ").append(radius).append(" around [").append(center.getX()).append(",").append(center.getY()).append("]):\n");
        asciiGrid.append("Legend: [C] City, [u] Our Unit, [E] Enemy Unit, [~] Water, [^] Mountain, [.] Plains/Grass, [F] Forest, [?] Fog\n\n");

        for (int y = minY; y <= maxY; y++) {
            StringBuilder line = new StringBuilder();
            line.append(String.format("%3d | ", y));
            for (int x = minX; x <= maxX; x++) {
                Tile tile = (tileMap != null) ? tileMap.getOrNull(x, y) : null;

                if (tile == null) {
                    line.append("   ");
                    continue;
                }

                if (!player.hasExplored(tile)) {
                    line.append(" ? ");
                    continue;
                }

                char symbol = '.';
                String terrain = tile.baseTerrain != null ? tile.baseTerrain : "";
                if (terrain.contains("Ocean") || terrain.contains("Coast") || terrain.contains("Water")) symbol = '~';
                else if (terrain.contains("Mountain")) symbol = '^';
                else if (terrain.contains("Hills")) symbol = 'h';
                else if (terrain.contains("Desert")) symbol = 'd';
                else if (tile.getTerrainFeatures().contains("Forest") || tile.getTerrainFeatures().contains("Jungle")) symbol = 'F';

                if (tile.isCityCenter()) {
                    symbol = 'C';
                } else if (tile.getMilitaryUnit() != null) {
                    symbol = (tile.getMilitaryUnit().getCiv() == player) ? 'u' : 'E';
                } else if (tile.getCivilianUnit() != null) {
                    symbol = (tile.getCivilianUnit().getCiv() == player) ? 's' : 'e';
                }

                line.append(" ").append(symbol).append(" ");

                // Add tile detail if explored
                Map<String, Object> td = new LinkedHashMap<>();
                td.put("x", x);
                td.put("y", y);
                td.put("terrain", tile.baseTerrain);
                td.put("features", new ArrayList<>(tile.getTerrainFeatures()));
                if (tile.getResource() != null) td.put("resource", tile.getResource());
                if (tile.getImprovement() != null) td.put("improvement", tile.getImprovement());
                if (tile.isCityCenter() && tile.getCity() != null) td.put("city", tile.getCity().getName());
                if (tile.getMilitaryUnit() != null) {
                    String civName = tile.getMilitaryUnit().getCiv() != null ? tile.getMilitaryUnit().getCiv().getCivName() : "Unknown";
                    td.put("military_unit", tile.getMilitaryUnit().getName() + " (" + civName + ")");
                }
                if (tile.getCivilianUnit() != null) {
                    String civName = tile.getCivilianUnit().getCiv() != null ? tile.getCivilianUnit().getCiv().getCivName() : "Unknown";
                    td.put("civilian_unit", tile.getCivilianUnit().getName() + " (" + civName + ")");
                }
                tileDetails.add(td);
            }
            asciiGrid.append(line).append("\n");
        }

        mapRes.put("ascii_view", asciiGrid.toString());
        mapRes.put("tiles", tileDetails);
        mapRes.put("center_x", center.getX());
        mapRes.put("center_y", center.getY());
        mapRes.put("radius", radius);

        return mapRes;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> parseSimpleJson(String json) {
        Map<String, Object> map = new HashMap<>();
        json = json.trim();
        if (json.startsWith("{") && json.endsWith("}")) {
            json = json.substring(1, json.length() - 1).trim();
        }
        
        int i = 0;
        int len = json.length();
        while (i < len) {
            while (i < len && (json.charAt(i) == ' ' || json.charAt(i) == ',' || json.charAt(i) == '\n' || json.charAt(i) == '\r')) i++;
            if (i >= len) break;

            if (json.charAt(i) != '"') break;
            i++;
            int keyStart = i;
            while (i < len && json.charAt(i) != '"') i++;
            String key = json.substring(keyStart, i);
            i++; // skip closing quote

            while (i < len && (json.charAt(i) == ' ' || json.charAt(i) == ':')) i++;
            if (i >= len) break;

            Object value;
            if (json.charAt(i) == '"') {
                i++;
                int valStart = i;
                StringBuilder sb = new StringBuilder();
                while (i < len && json.charAt(i) != '"') {
                    if (json.charAt(i) == '\\' && i + 1 < len) {
                        i++;
                        char esc = json.charAt(i);
                        if (esc == 'n') sb.append('\n');
                        else if (esc == 'r') sb.append('\r');
                        else if (esc == 't') sb.append('\t');
                        else sb.append(esc);
                    } else {
                        sb.append(json.charAt(i));
                    }
                    i++;
                }
                value = sb.toString();
                i++; // skip closing quote
            } else if (json.charAt(i) == '{') {
                int braceCount = 1;
                int valStart = i;
                i++;
                while (i < len && braceCount > 0) {
                    if (json.charAt(i) == '{') braceCount++;
                    else if (json.charAt(i) == '}') braceCount--;
                    i++;
                }
                value = parseSimpleJson(json.substring(valStart, i));
            } else {
                int valStart = i;
                while (i < len && json.charAt(i) != ',' && json.charAt(i) != '}') i++;
                String rawVal = json.substring(valStart, i).trim();
                if (rawVal.equalsIgnoreCase("true")) value = Boolean.TRUE;
                else if (rawVal.equalsIgnoreCase("false")) value = Boolean.FALSE;
                else if (rawVal.equalsIgnoreCase("null")) value = null;
                else {
                    try {
                        if (rawVal.contains(".")) value = Double.parseDouble(rawVal);
                        else value = Long.parseLong(rawVal);
                    } catch (Exception e) {
                        value = rawVal;
                    }
                }
            }
            map.put(key, value);
        }
        return map;
    }

    private static String toJson(Object obj) {
        if (obj == null) return "null";
        if (obj instanceof String) {
            String s = (String) obj;
            s = s.replace("\\", "\\\\")
                 .replace("\"", "\\\"")
                 .replace("\n", "\\n")
                 .replace("\r", "\\r")
                 .replace("\t", "\\t");
            return "\"" + s + "\"";
        }
        if (obj instanceof Number || obj instanceof Boolean) {
            return obj.toString();
        }
        if (obj instanceof Map) {
            Map<?, ?> m = (Map<?, ?>) obj;
            StringBuilder sb = new StringBuilder("{");
            boolean first = true;
            for (Map.Entry<?, ?> entry : m.entrySet()) {
                if (!first) sb.append(",");
                first = false;
                sb.append(toJson(entry.getKey().toString())).append(":").append(toJson(entry.getValue()));
            }
            sb.append("}");
            return sb.toString();
        }
        if (obj instanceof List) {
            List<?> list = (List<?>) obj;
            StringBuilder sb = new StringBuilder("[");
            boolean first = true;
            for (Object item : list) {
                if (!first) sb.append(",");
                first = false;
                sb.append(toJson(item));
            }
            sb.append("]");
            return sb.toString();
        }
        return "\"" + obj.toString() + "\"";
    }
}
