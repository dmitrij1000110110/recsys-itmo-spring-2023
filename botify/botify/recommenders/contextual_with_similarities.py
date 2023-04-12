from .random import Random
from .recommender import Recommender
import random

class ContextualWithSimilarities(Recommender):
    data = dict()

    similar_users = dict()

    def calc_similarity(self, a, b):
        ids = set()
        b1 = dict()
        res = 0.0
        for x in a:
            ids.add(x[0])
        for x in b:
            ids.add(x[0])
            b1[x[0]] = x[1]
        for x in a:
            track_id = x[0]
            y1 = x[1]
            if b1.__contains__(track_id):
                y2 = b1[track_id]
                res += abs(y1 - y2)
        return res

    def calc_similarities(self):
        self.similar_users.clear()
        uids = list(self.data.keys())
        for uid in uids:
            self.similar_users[uid] = list()
        n = len(uids)
        for i in range(n):
            for j in range(n):
                u1 = uids[i]
                u2 = uids[j]
                tracks1 = self.data[u1]
                tracks2 = self.data[u2]
                if len(tracks1) == 0 or len(tracks2) == 0:
                    continue
                diff = self.calc_similarity(tracks1, tracks2)
                self.similar_users[u1].append([diff, u2])
                self.similar_users[u2].append([diff, u1])
        for uid in uids:
            self.similar_users[uid].sort()
            sz = min(100, len(self.similar_users[uid]))
            self.similar_users[uid] = self.similar_users[uid][:sz]


    def __init__(self, tracks_redis, catalog, app):
        self.catalog = catalog
        self.random = Random(tracks_redis)
        self.tracks_redis = tracks_redis
        self.app = app

    def choose_track(self, list_prev_tracks, user):
        _, times_list = zip(*list_prev_tracks)
        times = dict()
        for p in list_prev_tracks:
            times[p[0]] = p[1]
        weights0 = dict()
        for track in list_prev_tracks:
            weights0[track[0]] = track[1]
        if self.similar_users.__contains__(user):
            total_similarity = 0.0
            for u1 in self.similar_users[user]:
                total_similarity += u1[0]
            if total_similarity > 0.0:
                for u1 in self.similar_users[user]:
                    k = u1[0] / total_similarity
                    for track in self.data[u1[1]]:
                        tid = track[0]
                        ttime = track[1]
                        if not weights0.__contains__(tid):
                            weights0[tid] = 0
                        weights0[tid] += ttime * k
        indexes = []
        weights = []
        for key in list(weights0.keys()):
            indexes.append(key)
            weights.append(weights0[key])
        res = random.choices(indexes, weights=weights)[0]
        return res

    def log(self, x):
        self.app.logger.info(x)

    def get_iterations(self):
        res = 0
        for key in list(self.data.keys()):
            res += len(self.data[key])
        return res

    def recommend_next(self, user: int, prev_track: int, prev_track_time: float) -> int:
        it = self.get_iterations()
        if not self.data.__contains__(user):
            self.data[user] = list()
        self.data[user].append([prev_track, prev_track_time])
        if it % 20 == 0:
            self.calc_similarities()
        base_track = self.choose_track(self.data[user], user)
        new_track_bytes = self.tracks_redis.get(base_track)
        if new_track_bytes is None:
            return self.random.recommend_next(user, base_track, 0)
        new_track = self.catalog.from_bytes(new_track_bytes)
        recommendations = new_track.recommendations
        if not recommendations:
            return self.random.recommend_next(user, base_track, 0)
        shuffled = list(recommendations)
        random.shuffle(shuffled)
        return shuffled[0]
