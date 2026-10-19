function X=noh(best_hyena_fitness)
min = 0.5;
max = 1;
count=0;
M=(max-min).*rand(1,1) + min;
M=M+best_hyena_fitness(1);

for i=2:numel(best_hyena_fitness)
    if M>=best_hyena_fitness(i)
        count=count+1;
    end
    
end
 
X=count;
clear count
clear M
clear px
count=0;
end

