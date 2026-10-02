import React, { useEffect, useRef, useState } from "react";
import { View, Text, StyleSheet, TouchableOpacity, Animated } from "react-native";
import { useWebSocket } from "../hooks/useWebSocket";
import ConnectionBadge from "../components/ConnectionBadge";
import type { EntryDisplayEvent, EntryDisplayUpdateEvent } from "../types";

interface Props {
  host: string;
  onBack: () => void;
}

export default function EntryDisplayScreen({ host, onBack }: Props) {
  const wsUrl = `ws://${host}/ws/entry-display`;
  const { status, lastEvent } = useWebSocket<EntryDisplayEvent>(wsUrl);

  const [state, setState] = useState<EntryDisplayUpdateEvent | null>(null);
  const [barrierPlate, setBarrierPlate] = useState<string | null>(null);
  const barrierAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!lastEvent) return;

    if (lastEvent.event === "entry_display_update") {
      setState(lastEvent);
    }

    if (lastEvent.event === "barrier_open" && lastEvent.gate === "entry") {
      setBarrierPlate(lastEvent.plate_number);
      Animated.sequence([
        Animated.timing(barrierAnim, { toValue: 1, duration: 200, useNativeDriver: true }),
        Animated.delay(2200),
        Animated.timing(barrierAnim, { toValue: 0, duration: 300, useNativeDriver: true }),
      ]).start(() => setBarrierPlate(null));
    }
  }, [lastEvent]);

  const freePaid = state?.free_paid_slots ?? "–";
  const totalPaid = state?.total_paid_slots ?? "–";
  const freeEmployee = state?.free_employee_slots ?? "–";
  const totalEmployee = state?.total_employee_slots ?? "–";
  const tariff = state?.tariff;

  return (
    <View style={styles.container}>
      <View style={styles.topBar}>
        <ConnectionBadge status={status} />
        <TouchableOpacity onPress={onBack}>
          <Text style={styles.backLink}>Настройки</Text>
        </TouchableOpacity>
      </View>

      <Text style={styles.heading}>Добро пожаловать</Text>
      <Text style={styles.subheading}>Свободные места</Text>

      <View style={styles.slotsRow}>
        <View style={[styles.slotCard, styles.paidCard]}>
          <Text style={styles.slotNumber}>
            {freePaid}
            <Text style={styles.slotTotal}> / {totalPaid}</Text>
          </Text>
          <Text style={styles.slotLabel}>ПЛАТНЫЕ места</Text>
        </View>

        <View style={[styles.slotCard, styles.employeeCard]}>
          <Text style={styles.slotNumber}>
            {freeEmployee}
            <Text style={styles.slotTotal}> / {totalEmployee}</Text>
          </Text>
          <Text style={styles.slotLabel}>СЛУЖЕБНЫЕ места</Text>
        </View>
      </View>

      <View style={styles.tariffBox}>
        <Text style={styles.tariffTitle}>Действующий тариф</Text>
        {tariff ? (
          <>
            <Text style={styles.tariffName}>{tariff.name}</Text>
            <Text style={styles.tariffPrice}>
              {tariff.price_per_minute.toFixed(2)} сом / мин
            </Text>
            {tariff.free_minutes > 0 && (
              <Text style={styles.tariffFree}>
                Первые {tariff.free_minutes} мин - бесплатно
              </Text>
            )}
          </>
        ) : (
          <Text style={styles.tariffName}>Загрузка тарифа…</Text>
        )}
      </View>

      {barrierPlate && (
        <Animated.View
          style={[
            styles.barrierOverlay,
            {
              opacity: barrierAnim,
              transform: [
                {
                  scale: barrierAnim.interpolate({
                    inputRange: [0, 1],
                    outputRange: [0.9, 1],
                  }),
                },
              ],
            },
          ]}
        >
          <Text style={styles.barrierEmoji}>⬆️</Text>
          <Text style={styles.barrierText}>Шлагбаум открыт</Text>
          <Text style={styles.barrierPlate}>{barrierPlate}</Text>
        </Animated.View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0f172a", padding: 20 },
  topBar: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  backLink: { color: "#60a5fa", fontSize: 13 },
  heading: { color: "#fff", fontSize: 26, fontWeight: "800", marginTop: 20 },
  subheading: { color: "#94a3b8", fontSize: 15, marginBottom: 16 },
  slotsRow: { flexDirection: "row", gap: 14 },
  slotCard: {
    flex: 1,
    borderRadius: 18,
    paddingVertical: 26,
    alignItems: "center",
  },
  paidCard: { backgroundColor: "#1d4ed8" },
  employeeCard: { backgroundColor: "#334155" },
  slotNumber: { color: "#fff", fontSize: 46, fontWeight: "900" },
  slotTotal: { fontSize: 22, fontWeight: "600", color: "rgba(255,255,255,0.7)" },
  slotLabel: { color: "rgba(255,255,255,0.85)", fontSize: 13, fontWeight: "700", marginTop: 6, letterSpacing: 0.5 },
  tariffBox: {
    marginTop: 24,
    backgroundColor: "#1e293b",
    borderRadius: 16,
    padding: 20,
  },
  tariffTitle: { color: "#94a3b8", fontSize: 13, fontWeight: "700", marginBottom: 6 },
  tariffName: { color: "#fff", fontSize: 17, fontWeight: "700" },
  tariffPrice: { color: "#4ade80", fontSize: 22, fontWeight: "800", marginTop: 6 },
  tariffFree: { color: "#fbbf24", fontSize: 13, marginTop: 4 },
  barrierOverlay: {
    position: "absolute",
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: "rgba(15,23,42,0.95)",
    alignItems: "center",
    justifyContent: "center",
  },
  barrierEmoji: { fontSize: 56 },
  barrierText: { color: "#4ade80", fontSize: 26, fontWeight: "800", marginTop: 12 },
  barrierPlate: { color: "#fff", fontSize: 18, marginTop: 8, letterSpacing: 2 },
});
