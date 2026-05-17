import time
from typing import List

from .config import OUTPUT_PER_GENS, PRECISION, REGRET, RCRS, RCRS_RANDOM, TD
from .operator import do_local_search, new_route_insertion, regret_insertion
from .solution import Solution
from . import state
from .util import argsort, mean, rand, randint
def update_best_solution(s, best_s, used, run, gen, data):
    if s.cost - best_s.cost < -PRECISION:
        best_s.copy_from(s)
        print("Best solution update: %.4f" % best_s.cost)
        state.find_best_time = used
        state.find_best_run = run
        state.find_best_gen = gen
        state.best_s_cost = best_s.cost
        if (not state.find_better) and (
            abs(best_s.cost - data.bks) < PRECISION or (best_s.cost - data.bks < -PRECISION)
        ):
            state.find_better = True
            state.find_bks_time = used
            state.find_bks_run = run
            state.find_bks_gen = gen


def initialization(pop, pop_fit, pop_argrank, data):
    length = len(pop)
    for i in range(length):
        pop[i].clear(data)
    print("Initialization, using %s method" % data.init)
    if data.init == RCRS:
        data.n_insert = RCRS
        data.ksize = data.k_init
        for i in range(length):
            data.lambda_gamma = data.latin[i]
            new_route_insertion(pop[i], data)
    elif data.init == RCRS_RANDOM:
        data.n_insert = RCRS
        data.ksize = data.k_init
        for i in range(length):
            data.lambda_gamma = (rand(0, 1, data.rng), rand(0, 1, data.rng))
            print("lambda, gamma: %f, %f" % data.lambda_gamma)
            new_route_insertion(pop[i], data)
    elif data.init == TD:
        data.ksize = data.k_init
        data.n_insert = TD
        for i in range(length):
            new_route_insertion(pop[i], data)
    else:
        pass

    for i in range(length):
        pop_fit[i] = pop[i].cost
        print("Solution %d, cost %.4f" % (i, pop_fit[i]))
    argsort(pop_fit, pop_argrank, length)
    print("Initialization done.")


def tournament(indice, pop_fit, boundray, data):
    index_index_1 = randint(0, boundray, data.rng)
    tmp = indice[index_index_1]
    indice[index_index_1] = indice[boundray]
    indice[boundray] = tmp
    index_index_2 = randint(0, boundray - 1, data.rng)
    tmp = indice[index_index_2]
    indice[index_index_2] = indice[boundray - 1]
    indice[boundray - 1] = tmp

    if abs(pop_fit[indice[boundray]] - pop_fit[indice[boundray - 1]]) < PRECISION:
        selected = randint(boundray - 1, boundray, data.rng)
    elif pop_fit[indice[boundray]] < pop_fit[indice[boundray - 1]]:
        selected = boundray
    else:
        selected = boundray - 1
    tmp = indice[selected]
    indice[selected] = indice[boundray]
    indice[boundray] = tmp


def select_parents(pop, pop_fit, p_indice, data):
    length = data.p_size
    indice = list(range(length))
    data.rng.shuffle(indice)
    if data.selection == "circle":
        for i in range(length - 1):
            p_indice[i] = (indice[i], indice[i + 1])
        p_indice[length - 1] = (indice[length - 1], indice[0])
    elif data.selection == "tournament":
        for i in range(length):
            tournament(indice, pop_fit, length - 1, data)
            tournament(indice, pop_fit, length - 2, data)
            p_indice[i] = (indice[length - 1], indice[length - 2])
    elif data.selection == "rdslection":
        for i in range(length):
            index_index_1 = randint(0, length - 1, data.rng)
            tmp = indice[index_index_1]
            indice[index_index_1] = indice[length - 1]
            indice[length - 1] = tmp
            index_index_2 = randint(0, length - 2, data.rng)
            p_indice[i] = (indice[length - 1], indice[index_index_2])
    else:
        pass


def update_candidate_routes(r, inserted, s, candidate_r, data):
    for node in r.node_list:
        inserted.add(node)
    i = 0
    length = len(candidate_r)
    while i < length:
        r_tmp = s.get(candidate_r[i])
        flag = True
        for node in r_tmp.node_list:
            if node == data.DC:
                continue
            if node in inserted:
                flag = False
                break
        if not flag:
            candidate_r.pop(i)
            length -= 1
        else:
            i += 1


def crossover(s1, s2, ch, data):
    if data.no_crossover:
        ch.copy_from(s1)
        return

    candidate_r_1 = list(range(s1.len()))
    candidate_r_2 = list(range(s2.len()))
    inserted = set()

    while True:
        if len(candidate_r_1) == 0:
            break
        selected = randint(0, len(candidate_r_1) - 1, data.rng)
        r_1 = s1.get(candidate_r_1[selected])
        ch.append(r_1)
        update_candidate_routes(r_1, inserted, s2, candidate_r_2, data)
        if len(candidate_r_2) == 0:
            break
        selected = randint(0, len(candidate_r_2) - 1, data.rng)
        r_2 = s2.get(candidate_r_2[selected])
        ch.append(r_2)
        update_candidate_routes(r_2, inserted, s1, candidate_r_1, data)

    if data.cross_repair == RCRS:
        data.n_insert = RCRS
        data.ksize = data.k_crossover
        data.lambda_gamma = (rand(0, 1, data.rng), rand(0, 1, data.rng))
        new_route_insertion(ch, data)
    elif data.cross_repair == TD:
        data.ksize = data.k_crossover
        data.n_insert = TD
        new_route_insertion(ch, data)
    elif data.cross_repair == REGRET:
        regret_insertion(ch, data)

    ch.cal_cost(data)


def crossover_population(pop, data, p_indice, child):
    print("Do crossover.")
    count = 0
    for indice_t in p_indice:
        if randint(0, 1, data.rng) == 0:
            crossover(pop[indice_t[0]], pop[indice_t[1]], child[count], data)
        else:
            crossover(pop[indice_t[1]], pop[indice_t[0]], child[count], data)
        count += 1


def output(pop, pop_fit, pop_argrank, data, output_complete=False):
    length = len(pop)
    best_cost = pop_fit[pop_argrank[0]]
    worst_cost = pop_fit[pop_argrank[length - 1]]
    avg_cost = mean(pop_fit, 0, length)
    print("Avg %.4f, Best %.4f, Worst %.4f" % (avg_cost, best_cost, worst_cost))
    if output_complete:
        pop[pop_argrank[0]].output(data)


def local_search(pop, pop_fit, pop_argrank, data):
    length = len(pop)
    for i in range(length):
        if rand(0, 1, data.rng) < data.ls_prob:
            do_local_search(pop[i], data)
            pop_fit[i] = pop[i].cost
    argsort(pop_fit, pop_argrank, length)


def replacement(pop, p_indice, child, pop_fit, pop_argrank, child_fit, child_argrank, data):
    length = len(child)
    if data.replacement == "one_on_one":
        for i in range(length):
            p_1_indice = p_indice[i][0]
            if child[i].cost - pop[p_1_indice].cost < -PRECISION:
                pop[p_1_indice].copy_from(child[i])
                pop_fit[p_1_indice] = pop[p_1_indice].cost
    elif data.replacement == "elitism":
        pop[length - 1].copy_from(pop[pop_argrank[0]])
        pop_fit[length - 1] = pop_fit[pop_argrank[0]]
        for i in range(length - 1):
            pop[i].copy_from(child[child_argrank[i]])
            pop_fit[i] = pop[i].cost
    else:
        pass
    for i in range(length):
        child[i].clear(data)


def search_framework(data, best_s):
    pop = [Solution(data) for _ in range(data.p_size)]
    child = [Solution(data) for _ in range(data.p_size)]

    pop_fit = [0.0 for _ in range(data.p_size)]
    child_fit = [0.0 for _ in range(data.p_size)]
    pop_argrank = [0 for _ in range(data.p_size)]
    child_argrank = [0 for _ in range(data.p_size)]

    p_indice = [(0, 0) for _ in range(data.p_size)]

    stime = time.process_time()
    used = 0

    time_exhausted = False
    run = 1
    while run <= data.runs:
        print("---------------------------------Run %d---------------------------" % run)
        no_improve = 0
        gen = 0
        initialization(pop, pop_fit, pop_argrank, data)
        used = int(time.process_time() - stime)
        print("already consumed %d sec" % used)

        local_search(pop, pop_fit, pop_argrank, data)
        used = int(time.process_time() - stime)
        print("already consumed %d sec" % used)

        print("After local search")
        output(pop, pop_fit, pop_argrank, data)
        cost_in_this_run = pop_fit[pop_argrank[0]]
        while no_improve <= data.g_1:
            gen += 1
            no_improve += 1
            select_parents(pop, pop_fit, p_indice, data)
            crossover_population(pop, data, p_indice, child)
            used = int(time.process_time() - stime)
            print("already consumed %d sec" % used)
            local_search(child, child_fit, child_argrank, data)
            replacement(pop, p_indice, child, pop_fit, pop_argrank, child_fit, child_argrank, data)
            argsort(pop_fit, pop_argrank, data.p_size)
            update_best_solution(pop[pop_argrank[0]], best_s, used, run, gen, data)
            if pop_fit[pop_argrank[0]] - cost_in_this_run < -PRECISION:
                no_improve = 0
                cost_in_this_run = pop_fit[pop_argrank[0]]

            used = int(time.process_time() - stime)
            if gen % OUTPUT_PER_GENS == 0:
                print("Gen: %d. " % gen, end="")
                output(pop, pop_fit, pop_argrank, data)
                print(
                    "Gen %d done, no improvement for %d gens, already consumed %d sec"
                    % (gen, no_improve, used)
                )

            if data.tmax != -1 and used > int(data.tmax):
                time_exhausted = True
                break
        print("Run %d finishes" % run)
        output(pop, pop_fit, pop_argrank, data)

        data.rng.seed(data.seed + run)
        if time_exhausted:
            break
        run += 1

    print("------------Summary-----------")
    print("Total %d runs, total consumed %d sec" % (run, int(used)))
    best_s.output(data)
    print(
        "In run %d, gen %d, find this solution, at time %d."
        % (state.find_best_run, state.find_best_gen, int(state.find_best_time))
    )
    print("Time to surpass BKS: %d." % int(state.find_bks_time))
    best_s.check(data)
